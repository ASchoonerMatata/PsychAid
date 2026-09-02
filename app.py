import os, sys, json, uuid, datetime, unicodedata

if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

from flask import Flask, render_template, request, jsonify, send_file
import io

app = Flask(__name__,
    template_folder=os.path.join(BASE_DIR, 'templates'),
    static_folder=os.path.join(BASE_DIR, 'static'))
app.secret_key = 'psychaid-secret-2024'
app.config['MAX_CONTENT_LENGTH'] = 25 * 1024 * 1024  # 25 MB upload limit

from scales_data import SCALES
from report_generator import (
    load_config, save_config, generate_report, report_to_docx,
    extract_text, load_skill_prompt
)
from providers import PROVIDERS, ProviderError, auth_status, resolve_provider
# pdf_forms imported lazily inside route — avoids Pillow arch crash at startup


# ── Security helpers ─────────────────────────────────────────────────────────

def _sanitize_download_name(value):
    value = value if isinstance(value, str) else ''
    value = ''.join(
        c for c in value
        if c not in '/\\' and not unicodedata.category(c).startswith('C')
    )
    return '_'.join(value.split())[:80] or 'Client'


@app.errorhandler(413)
def upload_too_large(error):
    return jsonify({'error': 'Uploaded files are too large (25 MB limit).'}), 413


# ── Session persistence ───────────────────────────────────────────────────────

SESSIONS_DIR = os.path.join(os.path.expanduser('~'), '.psychaid', 'sessions')
os.makedirs(SESSIONS_DIR, exist_ok=True)

_conversations = {}  # in-memory cache


def _session_path(sid):
    return os.path.join(SESSIONS_DIR, sid + '.json')


def _persist_session(sid):
    if sid not in _conversations:
        return
    conv = dict(_conversations[sid])
    conv['updated'] = datetime.datetime.now().isoformat()
    _conversations[sid]['updated'] = conv['updated']
    with open(_session_path(sid), 'w', encoding='utf-8') as f:
        json.dump(conv, f, ensure_ascii=False, indent=2)


def _load_session_from_disk(sid):
    path = _session_path(sid)
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    _conversations[sid] = data
    return data


def _list_sessions():
    out = []
    if not os.path.isdir(SESSIONS_DIR):
        return out
    for fname in os.listdir(SESSIONS_DIR):
        if not fname.endswith('.json'):
            continue
        try:
            with open(os.path.join(SESSIONS_DIR, fname), 'r', encoding='utf-8') as f:
                d = json.load(f)
            out.append({
                'session_id': d.get('session_id', fname[:-5]),
                'client_name': d.get('client_name', 'Unknown Client'),
                'started': d.get('started', ''),
                'updated': d.get('updated', d.get('started', '')),
                'turns': len([m for m in d.get('history', []) if m['role'] == 'assistant']),
            })
        except Exception:
            pass
    out.sort(key=lambda x: x['updated'], reverse=True)
    return out


# ── Multi-provider chat helper ────────────────────────────────────────────────

def _chat_turn(history, cfg, max_tokens=2000):
    """Generate one AI turn, supporting full message history for Anthropic
    and a flattened-history approach for other providers."""
    system = load_skill_prompt()
    provider_name = cfg.get('provider', 'anthropic')
    provider, api_key, model = resolve_provider(cfg)

    if provider_name == 'anthropic':
        import anthropic as _ant
        client = _ant.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model=model, max_tokens=max_tokens, system=system, messages=history
        )
        return resp.content[0].text
    else:
        # For providers without native multi-turn, flatten conversation
        conv_text = '\n\n'.join(
            f'{"Assistant" if m["role"] == "assistant" else "User"}: {m["content"]}'
            for m in history
        )
        return provider['generate'](system, conv_text, api_key, model)


# ── Page routes ───────────────────────────────────────────────────────────────

@app.route('/')
def index():
    cfg = load_config()
    return render_template('assessment.html', scales=SCALES, auth_status=auth_status(cfg))


@app.route('/assessment')
def assessment():
    cfg = load_config()
    return render_template('assessment.html', scales=SCALES, auth_status=auth_status(cfg))


@app.route('/settings')
def settings():
    cfg = load_config()
    provider_options = {
        name: {
            'label': p['label'],
            'default_model': p['default_model'],
            'auth_env': p['auth_env'],
            'docs_url': p['docs_url'],
            'has_saved_key': bool(cfg.get('api_keys', {}).get(name))
        }
        for name, p in PROVIDERS.items()
    }
    public_settings = {
        'provider': cfg.get('provider', 'anthropic'),
        'model': cfg.get('model', ''),
        'auth_mode': cfg.get('auth_mode', 'api_key')
    }
    return render_template('settings.html',
        provider_options=provider_options, settings=public_settings)


# ── Settings API ──────────────────────────────────────────────────────────────

@app.route('/api/save-settings', methods=['POST'])
def save_settings():
    data = request.get_json(silent=True) or {}
    provider = data.get('provider', '')
    auth_mode = data.get('auth_mode', '')
    if provider not in PROVIDERS:
        return jsonify({'error': 'Choose a valid AI provider.'}), 400
    if auth_mode not in ('api_key', 'subscription'):
        return jsonify({'error': 'Choose a valid authentication mode.'}), 400

    cfg = load_config()
    cfg['provider'] = provider
    cfg['model'] = data.get('model', '').strip() if isinstance(data.get('model'), str) else ''
    cfg['auth_mode'] = auth_mode

    new_keys = data.get('api_keys') if isinstance(data.get('api_keys'), dict) else {}
    for name, key in new_keys.items():
        if name in PROVIDERS and isinstance(key, str) and key.strip():
            cfg['api_keys'][name] = key.strip()

    save_config(cfg)
    return jsonify({
        'ok': True,
        'saved_keys': {name: bool(cfg['api_keys'].get(name)) for name in PROVIDERS}
    })


@app.route('/api/test-provider', methods=['POST'])
def test_provider():
    try:
        provider, api_key, model = resolve_provider(load_config())
        provider['generate'](
            'This is a connection test. Follow the user instruction exactly.',
            'Reply with only: OK',
            api_key, model
        )
        return jsonify({'ok': True, 'message': f'{provider["label"]} connection succeeded.'})
    except ProviderError as e:
        return jsonify({'error': str(e)}), 400


# ── One-shot report ───────────────────────────────────────────────────────────

@app.route('/api/generate-report', methods=['POST'])
def api_generate_report():
    uploads = request.files.getlist('files')
    if len(uploads) > 20:
        return jsonify({'error': 'No more than 20 files may be uploaded.'}), 400
    for f in uploads:
        if os.path.splitext(f.filename or '')[1].lower() not in ('.pdf', '.docx', '.txt'):
            return jsonify({'error': f'Unsupported file type for "{f.filename}".'}), 400
    files = [(f.filename, f.read()) for f in uploads]
    if not files:
        return jsonify({'error': 'No files uploaded.'}), 400
    cfg = load_config()
    try:
        report_text = generate_report(files, cfg)
        client_name = request.form.get('client_name', '')
        docx_bytes = report_to_docx(report_text, client_name)
        filename = f"{_sanitize_download_name(client_name)}_Report.docx"
        return send_file(io.BytesIO(docx_bytes),
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            as_attachment=True, download_name=filename)
    except ProviderError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── Interactive chat report ───────────────────────────────────────────────────

@app.route('/api/report/start', methods=['POST'])
def report_start():
    cfg = load_config()
    try:
        resolve_provider(cfg)  # validate config early
    except ProviderError as e:
        return jsonify({'error': str(e)}), 400

    client_name = request.form.get('client_name', '').strip()
    files = request.files.getlist('files')
    if not files or all(f.filename == '' for f in files):
        return jsonify({'error': 'Please upload at least one document.'}), 400

    doc_parts = []
    for f in files:
        try:
            data = f.read()
            text = extract_text(data, f.filename)
            doc_parts.append(f"=== {f.filename} ===\n{text.strip()}")
        except Exception as e:
            doc_parts.append(f"=== {f.filename} ===\n[Could not extract: {e}]")

    doc_combined = '\n\n'.join(doc_parts)
    label = f"for {client_name}" if client_name else "for this client"
    initial_msg = (
        f"Documents uploaded {label}:\n\n{doc_combined}\n\n"
        "Please begin the report drafting workflow."
    )

    session_id = str(uuid.uuid4())
    history = [{"role": "user", "content": initial_msg}]
    try:
        ai_msg = _chat_turn(history, cfg, max_tokens=2000)
    except ProviderError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    history.append({"role": "assistant", "content": ai_msg})
    now = datetime.datetime.now().isoformat()
    _conversations[session_id] = {
        "session_id": session_id,
        "history": history,
        "client_name": client_name,
        "started": now,
        "updated": now,
    }
    _persist_session(session_id)
    return jsonify({"session_id": session_id, "message": ai_msg})


@app.route('/api/report/message', methods=['POST'])
def report_message():
    cfg = load_config()
    data = request.get_json()
    session_id = data.get('session_id', '')
    user_msg = data.get('message', '').strip()

    if session_id not in _conversations:
        if _load_session_from_disk(session_id) is None:
            return jsonify({'error': 'Session not found. Please start a new report.'}), 404
    if not user_msg:
        return jsonify({'error': 'Empty message.'}), 400

    conv = _conversations[session_id]
    conv['history'].append({"role": "user", "content": user_msg})
    try:
        ai_msg = _chat_turn(conv['history'], cfg, max_tokens=2000)
    except ProviderError as e:
        conv['history'].pop()
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        conv['history'].pop()
        return jsonify({'error': str(e)}), 500

    conv['history'].append({"role": "assistant", "content": ai_msg})
    _persist_session(session_id)
    return jsonify({"message": ai_msg})


@app.route('/api/report/export', methods=['POST'])
def report_export():
    cfg = load_config()
    data = request.get_json()
    session_id = data.get('session_id', '')

    if session_id not in _conversations:
        if _load_session_from_disk(session_id) is None:
            return jsonify({'error': 'Session not found. Please start a new report.'}), 404

    conv = _conversations[session_id]

    # Collect all assistant messages and join them — no new AI call needed
    assistant_parts = [
        m['content'] for m in conv.get('history', [])
        if m.get('role') == 'assistant' and m.get('content', '').strip()
    ]
    report_text = '\n\n---\n\n'.join(assistant_parts)
    if not report_text.strip():
        return jsonify({'error': 'No report content found. Please generate the report first.'}), 400

    client_name = conv.get('client_name', '')
    docx_bytes = report_to_docx(report_text, client_name)
    filename = f"{_sanitize_download_name(client_name)}_Report.docx"
    return send_file(io.BytesIO(docx_bytes),
        mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        as_attachment=True, download_name=filename)


# ── Report library ────────────────────────────────────────────────────────────

@app.route('/api/sessions')
def api_list_sessions():
    return jsonify(_list_sessions())


@app.route('/api/sessions/<sid>/load', methods=['POST'])
def api_load_session(sid):
    conv = _conversations.get(sid) or _load_session_from_disk(sid)
    if conv is None:
        return jsonify({'error': 'Session not found'}), 404
    history = conv.get('history', [])
    display = history[1:] if history else []  # skip raw doc upload message
    return jsonify({
        'session_id': sid,
        'client_name': conv.get('client_name', ''),
        'started': conv.get('started', ''),
        'history': display,
    })


@app.route('/api/sessions/<sid>', methods=['DELETE'])
def api_delete_session(sid):
    _conversations.pop(sid, None)
    path = _session_path(sid)
    if os.path.exists(path):
        os.remove(path)
    return jsonify({'ok': True})


# ── PDF form downloads ────────────────────────────────────────────────────────

@app.route('/api/download-form/<sk>/<rater>')
def download_form(sk, rater):
    from pdf_forms import get_pdf_bytes  # lazy — avoids Pillow crash at startup
    client_name = request.args.get('name', 'Client')
    pdf_bytes = get_pdf_bytes(sk, rater, client_name=client_name)
    if pdf_bytes is None:
        return jsonify({'error': 'Form not found'}), 404
    scale_name = SCALES.get(sk, {}).get('name', sk.upper())
    fname = f"{_sanitize_download_name(client_name)}_{scale_name}_{rater.capitalize()}.pdf"
    return send_file(io.BytesIO(pdf_bytes), mimetype='application/pdf',
                     as_attachment=True, download_name=fname)


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5050, debug=False, threaded=True)

import os, sys, json

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

from scales_data import SCALES
from report_generator import load_config, save_config, generate_report, report_to_docx
from providers import PROVIDERS, ProviderError, resolve_provider
from pdf_forms import get_pdf_bytes

@app.route('/')
def index():
    return render_template('assessment.html', scales=SCALES)

@app.route('/assessment')
def assessment():
    return render_template('assessment.html', scales=SCALES)

@app.route('/settings')
def settings():
    cfg = load_config()
    provider_options = {
        name: {
            'label': provider['label'],
            'default_model': provider['default_model'],
            'auth_env': provider['auth_env'],
            'docs_url': provider['docs_url'],
            'has_saved_key': bool(cfg.get('api_keys', {}).get(name))
        }
        for name, provider in PROVIDERS.items()
    }
    public_settings = {
        'provider': cfg.get('provider', 'anthropic'),
        'model': cfg.get('model', ''),
        'auth_mode': cfg.get('auth_mode', 'api_key')
    }
    return render_template(
        'settings.html',
        provider_options=provider_options,
        settings=public_settings
    )

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
    current_key = data.get('api_key')
    if isinstance(current_key, str) and current_key.strip():
        new_keys[provider] = current_key
    for name, key in new_keys.items():
        if name in PROVIDERS and isinstance(key, str) and key.strip():
            cfg['api_keys'][name] = key.strip()

    save_config(cfg)
    return jsonify({
        'ok': True,
        'saved_keys': {
            name: bool(cfg['api_keys'].get(name)) for name in PROVIDERS
        }
    })

@app.route('/api/test-provider', methods=['POST'])
def test_provider():
    try:
        provider, api_key, model = resolve_provider(load_config())
        provider['generate'](
            'This is a connection test. Follow the user instruction exactly.',
            'Reply with only OK.',
            api_key,
            model
        )
        return jsonify({'ok': True, 'message': f'{provider["label"]} connection succeeded.'})
    except ProviderError as error:
        return jsonify({'error': str(error)}), 400

@app.route('/api/generate-report', methods=['POST'])
def api_generate_report():
    cfg = load_config()

    files = []
    for f in request.files.getlist('files'):
        files.append((f.filename, f.read()))
    
    if not files:
        return jsonify({'error': 'No files uploaded.'}), 400
    
    try:
        report_text = generate_report(files, cfg)
        client_name = request.form.get('client_name', '')
        docx_bytes = report_to_docx(report_text, client_name)
        
        filename = f"{client_name.replace(' ','_')}_Report.docx" if client_name else "PsychAid_Report.docx"
        return send_file(
            io.BytesIO(docx_bytes),
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            as_attachment=True,
            download_name=filename
        )
    except ProviderError as error:
        return jsonify({'error': str(error)}), 400
    except Exception as error:
        return jsonify({'error': str(error)}), 500

@app.route('/api/download-form/<sk>/<rater>')
def download_form(sk, rater):
    client_name = request.args.get('name', 'Client')
    pdf_bytes = get_pdf_bytes(sk, rater, client_name=client_name)
    if pdf_bytes is None:
        return jsonify({'error': 'Form not found'}), 404
    from scales_data import SCALES
    scale_name = SCALES.get(sk, {}).get('name', sk.upper())
    fname = f"{client_name.replace(' ','_')}_{scale_name}_{rater.capitalize()}.pdf"
    # Serve inline so native webview displays the PDF (user presses Back to return)
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=fname
    )

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5050, debug=False, threaded=True)

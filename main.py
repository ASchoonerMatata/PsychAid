import threading, time, sys, os, json, urllib.request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Loading screen shown immediately while Flask starts
LOADING_HTML = """<!DOCTYPE html><html><head><meta charset="UTF-8"><style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:system-ui,sans-serif;background:#1a2d4f;display:flex;align-items:center;justify-content:center;height:100vh;color:#fff}
.c{text-align:center}
.psi{font-size:3.5rem;font-family:Georgia,serif;opacity:.25;margin-bottom:14px}
h1{font-size:1.25rem;font-weight:700;letter-spacing:-.01em}
h1 span{color:#52b788}
p{font-size:.82rem;opacity:.45;margin-top:6px}
.bar{width:160px;height:3px;background:rgba(255,255,255,.12);border-radius:2px;margin:22px auto 0;overflow:hidden}
.fill{height:100%;background:#52b788;border-radius:2px;animation:ld 1.6s ease-in-out infinite}
@keyframes ld{0%{width:0;margin-left:0}50%{width:100%;margin-left:0}100%{width:0;margin-left:100%}}
</style></head><body><div class="c">
<div class="psi">Ψ</div>
<h1>Psych<span>Aid</span></h1>
<p>Starting up…</p>
<div class="bar"><div class="fill"></div></div>
</div></body></html>"""


def run_flask():
    from app import app
    app.run(host='127.0.0.1', port=5050, debug=False, threaded=True, use_reloader=False)


def _flask_ready(timeout=60):
    """Return True once Flask responds on port 5050."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen('http://127.0.0.1:5050/', timeout=1)
            return True
        except Exception:
            time.sleep(0.5)
    return False


def navigate_when_ready(window):
    """Poll Flask readiness in background, then navigate the window."""
    if _flask_ready():
        window.load_url('http://127.0.0.1:5050/')


# ── Self-test mode (used by CI to verify the build) ──────────────────────────
def _selftest():
    """Start Flask, verify it responds, print OK, exit 0. Used by CI."""
    t = threading.Thread(target=run_flask, daemon=True)
    t.start()
    if _flask_ready(timeout=30):
        try:
            r = urllib.request.urlopen('http://127.0.0.1:5050/', timeout=5)
            assert r.status == 200, f'Unexpected status {r.status}'
        except Exception as e:
            print(f'SELFTEST FAIL: {e}', file=sys.stderr)
            sys.exit(1)
        print('SELFTEST OK')
        sys.exit(0)
    else:
        print('SELFTEST FAIL: Flask did not start in time', file=sys.stderr)
        sys.exit(1)


# ── Native API (exposed to JS as window.pywebview.api) ───────────────────────
class PsychAidAPI:

    _current_session_id = None

    def download_form(self, sk, rater, client_name='Client'):
        import webview
        from pdf_forms import get_pdf_bytes
        from scales_data import SCALES
        pdf_bytes = get_pdf_bytes(sk, rater, client_name=client_name)
        if pdf_bytes is None:
            return {'error': 'Form not found'}
        scale_name = SCALES.get(sk, {}).get('name', sk.upper())
        default_name = f"{client_name.replace(' ', '_')}_{scale_name}_{rater.capitalize()}.pdf"
        result = webview.windows[0].create_file_dialog(
            dialog_type=webview.SAVE_DIALOG,
            directory=os.path.expanduser('~'),
            save_filename=default_name,
            file_types=('PDF Files (*.pdf)', 'All files (*.*)')
        )
        if result:
            filepath = result[0] if isinstance(result, (list, tuple)) else result
            if not str(filepath).lower().endswith('.pdf'):
                filepath = str(filepath) + '.pdf'
            with open(filepath, 'wb') as f:
                f.write(pdf_bytes)
            return {'success': True}
        return {'cancelled': True}

    def pick_files(self):
        """Open native file picker; return [{name, data (base64)}] for selected files."""
        import webview, base64
        result = webview.windows[0].create_file_dialog(
            dialog_type=webview.OPEN_DIALOG,
            allow_multiple=True,
            file_types=('Documents (*.pdf *.docx *.doc *.txt)', 'All Files (*.*)')
        )
        if not result:
            return {'files': []}
        files = []
        for path in result:
            try:
                with open(path, 'rb') as fh:
                    data = base64.b64encode(fh.read()).decode('utf-8')
                files.append({'name': os.path.basename(path), 'data': data})
            except Exception as e:
                files.append({'name': os.path.basename(path), 'error': str(e)})
        return {'files': files}

    def _docx_via_native_save(self, api_path, default_name):
        """POST to api_path, save result via native save dialog."""
        import webview, re
        try:
            payload = json.dumps({'session_id': '_placeholder'}).encode('utf-8')
        except Exception:
            pass
        try:
            req = urllib.request.Request(
                f'http://127.0.0.1:5050{api_path}',
                data=json.dumps({'session_id': self._current_session_id}).encode('utf-8'),
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                if resp.status != 200:
                    return {'error': f'Export failed (HTTP {resp.status})'}
                docx_bytes = resp.read()
                cd = resp.headers.get('Content-Disposition', '')
            m = re.search(r'filename[^;=\n]*=["\'"]?([^"\';\n]+)', cd)
            fname = m.group(1).strip() if m else default_name
        except Exception as e:
            return {'error': str(e)}

        result = webview.windows[0].create_file_dialog(
            dialog_type=webview.SAVE_DIALOG,
            directory=os.path.expanduser('~'),
            save_filename=fname,
            file_types=('Word Documents (*.docx)', 'All files (*.*)')
        )
        if result:
            filepath = result[0] if isinstance(result, (list, tuple)) else result
            if not str(filepath).lower().endswith('.docx'):
                filepath = str(filepath) + '.docx'
            with open(filepath, 'wb') as fh:
                fh.write(docx_bytes)
            return {'success': True}
        return {'cancelled': True}

    def set_session_id(self, session_id):
        """Called from JS to keep track of the active session for native exports."""
        self._current_session_id = session_id
        return {'ok': True}

    def download_report(self, session_id):
        """Export full report .docx via native save dialog."""
        import webview, re
        try:
            payload = json.dumps({'session_id': session_id}).encode('utf-8')
            req = urllib.request.Request(
                'http://127.0.0.1:5050/api/report/export',
                data=payload,
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                if resp.status != 200:
                    return {'error': f'Export failed (HTTP {resp.status})'}
                docx_bytes = resp.read()
                cd = resp.headers.get('Content-Disposition', '')
            m = re.search(r'filename[^;=\n]*=["\'"]?([^"\';\n]+)', cd)
            default_name = m.group(1).strip() if m else 'PsychAid_Report.docx'
        except Exception as e:
            return {'error': str(e)}

        result = webview.windows[0].create_file_dialog(
            dialog_type=webview.SAVE_DIALOG,
            directory=os.path.expanduser('~'),
            save_filename=default_name,
            file_types=('Word Documents (*.docx)', 'All files (*.*)')
        )
        if result:
            filepath = result[0] if isinstance(result, (list, tuple)) else result
            if not str(filepath).lower().endswith('.docx'):
                filepath = str(filepath) + '.docx'
            with open(filepath, 'wb') as f:
                f.write(docx_bytes)
            return {'success': True}
        return {'cancelled': True}

    def download_step_report(self, session_id):
        """Export STEP screening report .docx via native save dialog."""
        import webview, re
        try:
            payload = json.dumps({'session_id': session_id}).encode('utf-8')
            req = urllib.request.Request(
                'http://127.0.0.1:5050/api/report/export-step',
                data=payload,
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                if resp.status != 200:
                    return {'error': f'STEP export failed (HTTP {resp.status})'}
                docx_bytes = resp.read()
                cd = resp.headers.get('Content-Disposition', '')
            m = re.search(r'filename[^;=\n]*=["\'"]?([^"\';\n]+)', cd)
            default_name = m.group(1).strip() if m else 'PsychAid_STEP_Report.docx'
        except Exception as e:
            return {'error': str(e)}

        result = webview.windows[0].create_file_dialog(
            dialog_type=webview.SAVE_DIALOG,
            directory=os.path.expanduser('~'),
            save_filename=default_name,
            file_types=('Word Documents (*.docx)', 'All files (*.*)')
        )
        if result:
            filepath = result[0] if isinstance(result, (list, tuple)) else result
            if not str(filepath).lower().endswith('.docx'):
                filepath = str(filepath) + '.docx'
            with open(filepath, 'wb') as f:
                f.write(docx_bytes)
            return {'success': True}
        return {'cancelled': True}


def _show_webview_error(err):
    """Show a native error dialog when webview fails to start (Windows/Mac/Linux)."""
    msg = (
        f"PsychAid could not open its built-in window:\n\n{err}\n\n"
        "On Windows, make sure the Microsoft Edge WebView2 Runtime is installed.\n"
        "Download it from: https://developer.microsoft.com/microsoft-edge/webview2/"
    )
    try:
        # Try tkinter first (usually available)
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk(); root.withdraw()
        messagebox.showerror("PsychAid — Window Error", msg)
        root.destroy()
    except Exception:
        # Last resort: print to console
        print("WEBVIEW ERROR:", msg, file=sys.stderr)


if __name__ == '__main__':
    if '--selftest' in sys.argv:
        _selftest()

    # On Windows, force pywebview to use the EdgeChromium (WebView2) backend
    # before importing webview, so PyInstaller's collected modules are found.
    if sys.platform == 'win32':
        os.environ.setdefault('PYWEBVIEW_GUI', 'edgechromium')

    # Start Flask in background
    threading.Thread(target=run_flask, daemon=True).start()

    _webview_error = None
    try:
        import webview
        window = webview.create_window(
            'PsychAid',
            html=LOADING_HTML,
            js_api=PsychAidAPI(),
            width=1280, height=820,
            min_size=(900, 600)
        )
        threading.Thread(target=navigate_when_ready, args=(window,), daemon=True).start()
        webview.start()
    except Exception as e:
        _webview_error = e

    if _webview_error is not None:
        _show_webview_error(_webview_error)
        # Only fall back to browser on non-Windows; on Windows show the error
        # so the user knows they need the WebView2 runtime.
        if sys.platform != 'win32':
            _flask_ready(timeout=60)
            import webbrowser
            webbrowser.open('http://127.0.0.1:5050')
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                sys.exit(0)

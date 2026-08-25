import threading, time, sys, os, socket

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

def _free_port():
    # ponytail: bind-then-release race is fine on loopback; switch to passing the
    # live socket into Flask if a collision ever actually shows up.
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    return port

PORT = _free_port()
URL = f'http://127.0.0.1:{PORT}'

def run_flask():
    from app import app
    app.run(host='127.0.0.1', port=PORT, debug=False, threaded=True, use_reloader=False)


class PsychAidAPI:
    """Exposed to JS as window.pywebview.api — handles native file dialogs."""

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


def selftest():
    """Prove a packaged build has every dependency and data file it needs."""
    from app import app
    from scales_data import SCALES
    from pdf_forms import get_pdf_bytes
    from report_generator import report_to_docx
    c = app.test_client()
    assert c.get('/').status_code == 200, 'index failed'
    assert c.get('/settings').status_code == 200, 'settings failed'
    sk = next(iter(SCALES))
    pdf = next((b for r in ('self', 'parent', 'teacher')
                if (b := get_pdf_bytes(sk, r, client_name='Test'))), None)
    assert pdf and pdf[:4] == b'%PDF', f'no PDF produced for {sk}'
    assert report_to_docx('Hello', 'Test')[:2] == b'PK', 'no DOCX produced'
    print('selftest OK')


if __name__ == '__main__':
    if '--selftest' in sys.argv:
        selftest()
        sys.exit(0)

    threading.Thread(target=run_flask, daemon=True).start()

    import urllib.request
    for _ in range(60):
        try:
            urllib.request.urlopen(URL, timeout=1)
            break
        except:
            time.sleep(0.5)

    try:
        import webview
        webview.create_window(
            'PsychAid',
            URL,
            js_api=PsychAidAPI(),
            width=1280, height=820,
            min_size=(900, 600)
        )
        webview.start()
    except Exception as e:
        import webbrowser
        webbrowser.open(URL)
        try:
            while True: time.sleep(1)
        except KeyboardInterrupt:
            sys.exit(0)

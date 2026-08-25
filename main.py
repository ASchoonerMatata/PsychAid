import threading, time, sys, os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

def run_flask():
    from app import app
    app.run(host='127.0.0.1', port=5050, debug=False, threaded=True, use_reloader=False)


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


if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()

    import urllib.request
    for _ in range(60):
        try:
            urllib.request.urlopen('http://127.0.0.1:5050', timeout=1)
            break
        except:
            time.sleep(0.5)

    try:
        import webview
        webview.create_window(
            'PsychAid',
            'http://127.0.0.1:5050',
            js_api=PsychAidAPI(),
            width=1280, height=820,
            min_size=(900, 600)
        )
        webview.start()
    except Exception as e:
        import webbrowser
        webbrowser.open('http://127.0.0.1:5050')
        try:
            while True: time.sleep(1)
        except KeyboardInterrupt:
            sys.exit(0)

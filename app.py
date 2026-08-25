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
    return render_template('settings.html', api_key=cfg.get('api_key', ''))

@app.route('/api/save-settings', methods=['POST'])
def save_settings():
    data = request.get_json()
    cfg = load_config()
    cfg['api_key'] = data.get('api_key', '').strip()
    save_config(cfg)
    return jsonify({'ok': True})

@app.route('/api/generate-report', methods=['POST'])
def api_generate_report():
    cfg = load_config()
    api_key = cfg.get('api_key', '')
    if not api_key:
        return jsonify({'error': 'No API key configured. Go to Settings to add your Anthropic API key.'}), 400
    
    files = []
    for f in request.files.getlist('files'):
        files.append((f.filename, f.read()))
    
    if not files:
        return jsonify({'error': 'No files uploaded.'}), 400
    
    try:
        report_text = generate_report(files, api_key)
        client_name = request.form.get('client_name', '')
        docx_bytes = report_to_docx(report_text, client_name)
        
        filename = f"{client_name.replace(' ','_')}_Report.docx" if client_name else "PsychAid_Report.docx"
        return send_file(
            io.BytesIO(docx_bytes),
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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

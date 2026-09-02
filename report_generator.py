import os, json, platform, io, sys, tempfile

from providers import resolve_provider

def _config_path():
    s = platform.system()
    if s == 'Windows':
        base = os.environ.get('APPDATA', os.path.expanduser('~'))
    elif s == 'Darwin':
        base = os.path.expanduser('~/Library/Application Support')
    else:
        base = os.path.expanduser('~/.config')
    return os.path.join(base, 'PsychAid', 'config.json')

def load_config():
    p = _config_path()
    if os.path.exists(p):
        with open(p) as f:
            raw = json.load(f)
        cfg = _normalise_config(raw)
        if cfg != raw:
            save_config(cfg)
        return cfg
    return _normalise_config({})

def save_config(data):
    p = _config_path()
    directory = os.path.dirname(p)
    os.makedirs(directory, mode=0o700, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(dir=directory)
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(_normalise_config(data), f)
        try:
            os.chmod(temp_path, 0o600)
        except OSError:
            pass
        os.replace(temp_path, p)
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise

def _normalise_config(data):
    data = data if isinstance(data, dict) else {}
    keys = data.get('api_keys') if isinstance(data.get('api_keys'), dict) else {}
    keys = {
        name: value for name, value in keys.items()
        if isinstance(name, str) and isinstance(value, str)
    }

    legacy_key = data.get('api_key')
    if isinstance(legacy_key, str) and legacy_key.strip() and not keys.get('anthropic'):
        keys['anthropic'] = legacy_key.strip()

    provider = data.get('provider') if isinstance(data.get('provider'), str) else 'anthropic'
    model = data.get('model') if isinstance(data.get('model'), str) else ''
    auth_mode = data.get('auth_mode') if data.get('auth_mode') in ('api_key', 'subscription') else 'api_key'
    return {
        'provider': provider or 'anthropic',
        'model': model.strip(),
        'auth_mode': auth_mode,
        'api_keys': keys
    }

def extract_text(file_bytes, filename):
    ext = os.path.splitext(filename)[1].lower()
    if ext == '.pdf':
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        return '\n'.join(p.extract_text() or '' for p in reader.pages)
    elif ext == '.docx':
        import mammoth
        result = mammoth.extract_raw_text(io.BytesIO(file_bytes))
        return result.value
    else:
        return file_bytes.decode('utf-8', errors='replace')

SYSTEM_PROMPT = """You are a clinical report assistant for an Australian psychology practice. 
You receive assessment documents, intake forms, and score reports uploaded by a psychologist. 
Your task is to synthesise the information into a structured psychological report.

Structure the report with these sections:
1. Identifying Information
2. Reason for Referral
3. Background History (developmental, medical, educational, family/social)
4. Assessment Measures Administered
5. Behavioural Observations (leave placeholder: [To be completed by clinician])
6. Assessment Results (leave placeholder: [To be completed by clinician])
7. Summary and Diagnostic Impressions (leave placeholder: [To be completed by clinician])
8. Recommendations

For the Recommendations section, include relevant recommendations based on the profile presented.
Use professional clinical language appropriate for Australian psychological practice.
Do not fabricate information not present in the source documents."""

_SKILL_PROMPT = None

def load_skill_prompt():
    global _SKILL_PROMPT
    if _SKILL_PROMPT is not None:
        return _SKILL_PROMPT

    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base, 'skill', '4thought-report', 'SKILL.md')

    try:
        with open(path, encoding='utf-8') as f:
            text = f.read()
        lines = text.splitlines(keepends=True)
        delimiters = [i for i, line in enumerate(lines) if line.strip() == '---']
        if delimiters and delimiters[0] == 0 and len(delimiters) > 1:
            text = ''.join(lines[delimiters[1] + 1:])
        _SKILL_PROMPT = text or SYSTEM_PROMPT
    except (OSError, UnicodeError):
        _SKILL_PROMPT = SYSTEM_PROMPT
    return _SKILL_PROMPT

def generate_report(files, cfg):
    all_text = []
    for fname, fbytes in files:
        try:
            text = extract_text(fbytes, fname)
            all_text.append(f"=== {fname} ===\n{text}")
        except Exception as e:
            all_text.append(f"=== {fname} ===\n[Error extracting: {e}]")
    
    combined = '\n\n'.join(all_text)
    
    provider, api_key, model = resolve_provider(cfg)
    return provider['generate'](
        load_skill_prompt(),
        f"Please generate a psychological report based on the following documents:\n\n{combined}",
        api_key,
        model
    )

def report_to_docx(text, client_name=''):
    import re
    from docx import Document
    from docx.shared import Pt, RGBColor, Inches
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from lxml import etree

    DARK = RGBColor(0x26, 0x26, 0x26)
    FONT = 'Cambria'
    BODY_PT = Pt(11)
    HEAD_PT = Pt(11)

    # ── Load the branded template ────────────────────────────────────────────
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    template_path = os.path.join(base, 'report_template.docx')

    try:
        doc = Document(template_path)
    except Exception:
        doc = Document()

    body = doc.element.body
    children = list(body)

    # Identify the footer text paragraphs (last 2 paragraphs with text before sectPr)
    # and the header image paragraph (index 1). Clear everything in between.
    HEADER_IDX = 1  # paragraph with floating header image
    W_NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'

    # Find footer paras (ones with text near the end)
    footer_indices = []
    for idx, child in enumerate(children):
        t = ''.join(n.text or '' for n in child.iter('{%s}t' % W_NS))
        if t.strip() and idx > len(children) // 2:
            footer_indices.append(idx)

    # Remove all paragraphs between header image and footer
    keep = set([0, HEADER_IDX] + footer_indices + [len(children) - 1])
    to_remove = [c for i, c in enumerate(children)
                 if i not in keep and c.tag.split('}')[-1] in ('p', 'tbl')]
    for el in to_remove:
        body.remove(el)

    # Find insertion point: after header image paragraph, before footer text
    children = list(body)
    insert_before = None
    for idx, child in enumerate(children):
        t = ''.join(n.text or '' for n in child.iter('{%s}t' % W_NS))
        if t.strip():  # first paragraph with text = start of footer
            insert_before = child
            break
    if insert_before is None:
        insert_before = body.find('{%s}sectPr' % W_NS)

    def _insert(el):
        body.insert(list(body).index(insert_before), el)

    # ── Helpers ──────────────────────────────────────────────────────────────
    def _new_para(style_name=None):
        from docx.oxml.ns import qn
        p = OxmlElement('w:p')
        if style_name:
            pPr = OxmlElement('w:pPr')
            pStyle = OxmlElement('w:pStyle')
            pStyle.set(qn('w:val'), style_name)
            pPr.append(pStyle)
            p.append(pPr)
        return p

    def _new_run(p_el, txt, bold=False, size_pt=None):
        from docx.oxml.ns import qn
        r = OxmlElement('w:r')
        rPr = OxmlElement('w:rPr')
        rFonts = OxmlElement('w:rFonts')
        rFonts.set(qn('w:ascii'), FONT)
        rFonts.set(qn('w:hAnsi'), FONT)
        rPr.append(rFonts)
        if bold:
            b = OxmlElement('w:b'); rPr.append(b)
        sz = OxmlElement('w:sz')
        sz.set(qn('w:val'), str(int((size_pt or BODY_PT.pt) * 2)))
        rPr.append(sz)
        color = OxmlElement('w:color')
        color.set(qn('w:val'), '262626')
        rPr.append(color)
        r.append(rPr)
        t = OxmlElement('w:t')
        t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
        t.text = txt
        r.append(t)
        p_el.append(r)
        return r

    def _add_bold_runs_xml(p_el, raw):
        parts = re.split(r'(\*\*[^*]+\*\*)', raw)
        for part in parts:
            if part.startswith('**') and part.endswith('**'):
                _new_run(p_el, part[2:-2], bold=True)
            elif part:
                _new_run(p_el, part, bold=False)

    def _spacing(p_el, before=0, after=4):
        from docx.oxml.ns import qn
        pPr = p_el.find('{%s}pPr' % W_NS)
        if pPr is None:
            pPr = OxmlElement('w:pPr')
            p_el.insert(0, pPr)
        sp = OxmlElement('w:spacing')
        sp.set(qn('w:before'), str(int(before * 20)))
        sp.set(qn('w:after'), str(int(after * 20)))
        pPr.append(sp)

    def add_heading(text_content):
        clean = re.sub(r'^#+\s*', '', text_content).strip()
        p = _new_para()
        _spacing(p, before=10, after=2)
        _new_run(p, clean, bold=True, size_pt=HEAD_PT.pt)
        _insert(p)

    def add_body(text_content):
        p = _new_para()
        _spacing(p, before=0, after=4)
        _add_bold_runs_xml(p, text_content)
        _insert(p)

    def add_bullet(text_content):
        p = _new_para(style_name='ListBullet')
        _spacing(p, before=0, after=2)
        _add_bold_runs_xml(p, text_content)
        _insert(p)

    def add_table(rows):
        if not rows:
            return
        from docx.oxml.ns import qn
        cols = max(len(r) for r in rows)
        tbl = OxmlElement('w:tbl')
        tblPr = OxmlElement('w:tblPr')
        tblBorders = OxmlElement('w:tblBorders')
        for side in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
            b = OxmlElement(f'w:{side}')
            b.set(qn('w:val'), 'single')
            b.set(qn('w:sz'), '4')
            b.set(qn('w:color'), '262626')
            tblBorders.append(b)
        tblPr.append(tblBorders)
        tbl.append(tblPr)
        for ri, row_data in enumerate(rows):
            tr = OxmlElement('w:tr')
            for ci in range(cols):
                tc = OxmlElement('w:tc')
                p = OxmlElement('w:p')
                cell_text = row_data[ci].strip() if ci < len(row_data) else ''
                _new_run(p, cell_text, bold=(ri == 0))
                tc.append(p)
                tr.append(tc)
            tbl.append(tr)
        _insert(tbl)
        spacer = _new_para()
        _spacing(spacer, before=0, after=4)
        _insert(spacer)

    # ── Parse and render ─────────────────────────────────────────────────────
    # Add a spacer after header image
    spacer = _new_para()
    _spacing(spacer, before=0, after=8)
    _insert(spacer)

    lines = text.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            p = _new_para(); _spacing(p, 0, 2); _insert(p)
            i += 1; continue

        if re.match(r'^-{3,}$', stripped) or re.match(r'^\*{3,}$', stripped):
            i += 1; continue

        if stripped.startswith('|') and stripped.endswith('|'):
            table_rows = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                row = lines[i].strip()
                if re.match(r'^\|[\s|:-]+\|$', row):
                    i += 1; continue
                cells = [c.strip() for c in row.strip('|').split('|')]
                table_rows.append(cells)
                i += 1
            add_table(table_rows)
            continue

        if re.match(r'^#{1,3}\s', stripped):
            add_heading(stripped); i += 1; continue

        if (stripped.isupper() and len(stripped) > 3
                and not stripped.startswith('-')
                and not re.match(r'^\d+[\.\)]\s', stripped)):
            add_heading(stripped); i += 1; continue

        if re.match(r'^[-*•]\s+', stripped):
            add_bullet(re.sub(r'^[-*•]\s+', '', stripped)); i += 1; continue

        if re.match(r'^\d+[\.\)]\s+', stripped):
            add_bullet(re.sub(r'^\d+[\.\)]\s+', '', stripped)); i += 1; continue

        add_body(stripped); i += 1

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.read()

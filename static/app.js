let fileList = [];

function initDrop() {
    const zone = document.getElementById('drop-zone');
    if (!zone) return;
    zone.addEventListener('click', () => document.getElementById('file-input').click());
    zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('drag-over'); });
    zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
    zone.addEventListener('drop', e => { e.preventDefault(); zone.classList.remove('drag-over'); addFiles(e.dataTransfer.files); });
    document.getElementById('file-input').addEventListener('change', e => addFiles(e.target.files));
}

function addFiles(files) {
    for (const f of files) {
        if (!fileList.find(x => x.name === f.name && x.size === f.size)) fileList.push(f);
    }
    renderFileList();
}

function removeFile(idx) { fileList.splice(idx, 1); renderFileList(); }

function renderFileList() {
    const el = document.getElementById('file-list');
    if (!el) return;
    el.innerHTML = fileList.map((f, i) => `
        <div class="file-item">
            <span>📄</span>
            <span>${f.name}</span>
            <span style="color:var(--muted);font-size:.8rem">${(f.size/1024).toFixed(1)} KB</span>
            <button onclick="removeFile(${i})" title="Remove">✕</button>
        </div>`).join('');
}

// Navigate to PDF — displays inline in webview, Back button returns to home
function downloadForm(sk, rater) {
    const clientName = (document.getElementById('report-client-name') || {}).value || '';
    const url = `/api/download-form/${sk}/${rater}?name=${encodeURIComponent(clientName)}`;
    window.location.href = url;
}

async function generateReport() {
    if (fileList.length === 0) { showToast('Please upload at least one document.', 'error'); return; }
    const btn = document.getElementById('generate-btn');
    btn.classList.add('generating'); btn.disabled = true;
    showToast('Generating report… this may take 30–60 seconds.', 'info');

    const fd = new FormData();
    fileList.forEach(f => fd.append('files', f));
    const cn = document.getElementById('report-client-name');
    if (cn) fd.append('client_name', cn.value);

    try {
        const res = await fetch('/api/generate-report', { method: 'POST', body: fd });
        if (!res.ok) {
            const j = await res.json().catch(() => ({}));
            throw new Error(j.error || `Server error ${res.status}`);
        }
        const blob = await res.blob();
        const cd = res.headers.get('Content-Disposition') || '';
        const m = cd.match(/filename[^;=\n]*=["']?([^"';\n]+)/);
        const fname = m ? m[1] : 'PsychAid_Report.docx';
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a'); a.href = url; a.download = fname; a.click();
        URL.revokeObjectURL(url);
        showToast('Report downloaded!', 'success');
    } catch (e) {
        showToast(e.message, 'error');
    } finally {
        btn.classList.remove('generating'); btn.disabled = false;
    }
}

function showToast(msg, type = 'info') {
    let t = document.getElementById('toast');
    if (!t) { t = document.createElement('div'); t.id = 'toast'; t.className = 'toast'; document.body.appendChild(t); }
    t.textContent = msg; t.className = `toast ${type}`;
    requestAnimationFrame(() => requestAnimationFrame(() => t.classList.add('show')));
    clearTimeout(t._to); t._to = setTimeout(() => t.classList.remove('show'), 4000);
}

document.addEventListener('DOMContentLoaded', initDrop);

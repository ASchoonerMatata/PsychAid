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
    el.replaceChildren();
    fileList.forEach((f, i) => {
        const item = document.createElement('div');
        item.className = 'file-item';

        const icon = document.createElement('span');
        icon.textContent = '📄';
        const name = document.createElement('span');
        name.textContent = f.name;
        const size = document.createElement('span');
        size.style.cssText = 'color:var(--muted);font-size:.8rem';
        size.textContent = `${(f.size/1024).toFixed(1)} KB`;
        const remove = document.createElement('button');
        remove.title = 'Remove';
        remove.textContent = '✕';
        remove.addEventListener('click', () => removeFile(i));

        item.append(icon, name, size, remove);
        el.appendChild(item);
    });
}

// The webview has no download handler, so an attachment navigation is silently
// dropped. Use the native save dialog main.py exposes; fall back to a plain
// navigation only in browser-fallback mode, where the browser does handle it.
function downloadForm(sk, rater) {
    const clientName = (document.getElementById('report-client-name') || {}).value || '';
    if (window.pywebview && window.pywebview.api) {
        window.pywebview.api.download_form(sk, rater, clientName || 'Client')
            .then(r => {
                if (r.success) showToast('Form saved.', 'success');
                else if (r.error) showToast(r.error, 'error');
            })
            .catch(e => showToast(`Could not save form: ${e}`, 'error'));
        return;
    }
    window.location.href = `/api/download-form/${sk}/${rater}?name=${encodeURIComponent(clientName)}`;
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

let providerOptions = {};
let savedKeys = {};
let pendingKeys = {};
let pendingModels = {};
let previousProvider = '';

function initSettings() {
    const form = document.getElementById('settings-form');
    if (!form) return;

    providerOptions = JSON.parse(form.dataset.providers);
    const settings = JSON.parse(form.dataset.settings);
    savedKeys = Object.fromEntries(
        Object.entries(providerOptions).map(([name, provider]) => [name, provider.has_saved_key])
    );
    previousProvider = settings.provider;

    document.getElementById('provider').addEventListener('change', updateProviderFields);
    document.querySelectorAll('input[name="auth-mode"]').forEach(input => {
        input.addEventListener('change', updateAuthFields);
    });
    updateProviderFields();
    updateAuthFields();
}

function updateProviderFields() {
    const providerSelect = document.getElementById('provider');
    const keyInput = document.getElementById('api-key');
    if (!providerSelect || !keyInput) return;

    if (previousProvider) pendingKeys[previousProvider] = keyInput.value;
    const model = document.getElementById('model');
    if (previousProvider) pendingModels[previousProvider] = model.value;
    const providerName = providerSelect.value;
    const provider = providerOptions[providerName];
    previousProvider = providerName;
    keyInput.value = pendingKeys[providerName] || '';
    model.value = pendingModels[providerName] || '';
    keyInput.placeholder = `Enter a new ${provider.label} key`;

    const status = document.getElementById('key-status');
    status.textContent = savedKeys[providerName] ? 'A key is saved' : 'No key saved';
    status.classList.toggle('has-key', savedKeys[providerName]);

    model.placeholder = provider.default_model;
    document.getElementById('default-model').textContent = provider.default_model;
    document.getElementById('subscription-help').textContent =
        `Use the ${provider.auth_env} environment variable configured on this computer.`;
}

function updateAuthFields() {
    const mode = document.querySelector('input[name="auth-mode"]:checked')?.value;
    const keyGroup = document.getElementById('api-key-group');
    if (keyGroup) keyGroup.hidden = mode !== 'api_key';
}

async function saveSettings() {
    const provider = document.getElementById('provider').value;
    const keyInput = document.getElementById('api-key');
    pendingKeys[provider] = keyInput.value;
    const apiKeys = Object.fromEntries(
        Object.entries(pendingKeys)
            .map(([name, key]) => [name, key.trim()])
            .filter(([, key]) => key)
    );
    const payload = {
        provider,
        model: document.getElementById('model').value.trim(),
        auth_mode: document.querySelector('input[name="auth-mode"]:checked').value,
        api_keys: apiKeys
    };

    try {
        const res = await fetch('/api/save-settings', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.error || 'Could not save settings.');

        savedKeys = data.saved_keys;
        pendingKeys = {};
        previousProvider = provider;
        keyInput.value = '';
        updateProviderFields();
        showToast('Settings saved!', 'success');
    } catch (error) {
        showToast(error.message, 'error');
    }
}

async function testProvider() {
    const button = document.getElementById('test-provider-btn');
    button.disabled = true;
    button.classList.add('testing');
    try {
        const res = await fetch('/api/test-provider', {method: 'POST'});
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.error || `Server error ${res.status}`);
        showToast(data.message, 'success');
    } catch (error) {
        showToast(error.message, 'error');
    } finally {
        button.disabled = false;
        button.classList.remove('testing');
    }
}

document.addEventListener('DOMContentLoaded', () => {
    initDrop();
    initSettings();
});

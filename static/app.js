// PsychAid — shared utilities

// ── Toast ────────────────────────────────────────────────────────────────────
function showToast(msg, type) {
  type = type || 'info';
  var t = document.getElementById('toast');
  if (!t) return;
  t.textContent = msg;
  t.className = 'toast ' + type;
  requestAnimationFrame(function() {
    requestAnimationFrame(function() { t.classList.add('show'); });
  });
  clearTimeout(t._to);
  t._to = setTimeout(function() { t.classList.remove('show'); }, 4000);
}

// ── Screener download ────────────────────────────────────────────────────────
function downloadForm(sk, rater) {
  const clientName = (document.getElementById('client-name') || {}).value || '';
  const menu = document.getElementById('screeners-menu');
  if (menu) menu.classList.remove('open');

  if (window.pywebview && window.pywebview.api) {
    showToast('Opening save dialog…', 'info');
    window.pywebview.api.download_form(sk, rater, clientName)
      .then(r => {
        if (r && r.success) showToast('PDF saved!', 'success');
        else if (r && r.cancelled) {}
        else if (r && r.error) showToast(r.error, 'error');
      })
      .catch(() => showToast('Could not save PDF.', 'error'));
  } else {
    const url = '/api/download-form/' + sk + '/' + rater + '?name=' + encodeURIComponent(clientName);
    window.location.href = url;
  }
}

// ── Settings page ────────────────────────────────────────────────────────────
let _providerOptions = {};
let _savedKeys = {};
let _pendingKeys = {};
let _previousProvider = '';

function initSettings() {
  const form = document.getElementById('settings-form');
  if (!form) return;

  _providerOptions = JSON.parse(form.dataset.providers);
  const settings = JSON.parse(form.dataset.settings);
  _savedKeys = Object.fromEntries(
    Object.entries(_providerOptions).map(([name, p]) => [name, p.has_saved_key])
  );
  _previousProvider = settings.provider;

  document.getElementById('provider').addEventListener('change', updateProviderFields);
  document.querySelectorAll('input[name="auth-mode"]').forEach(input => {
    input.addEventListener('change', updateAuthFields);
  });
  updateProviderFields();
  updateAuthFields();
}

function updateProviderFields() {
  const sel = document.getElementById('provider');
  const keyInput = document.getElementById('api-key');
  if (!sel || !keyInput) return;

  if (_previousProvider) _pendingKeys[_previousProvider] = keyInput.value;
  const name = sel.value;
  const p = _providerOptions[name];
  _previousProvider = name;
  keyInput.value = _pendingKeys[name] || '';
  keyInput.placeholder = `Enter a new ${p.label} key`;

  const status = document.getElementById('key-status');
  if (status) {
    status.textContent = _savedKeys[name] ? 'Key saved ✓' : 'No key saved';
    status.className = 'key-status' + (_savedKeys[name] ? ' has-key' : '');
  }
  const dm = document.getElementById('default-model');
  if (dm) dm.textContent = p.default_model;
  const sh = document.getElementById('subscription-help');
  if (sh) sh.textContent = `Uses the ${p.auth_env} environment variable on this machine.`;
}

function updateAuthFields() {
  const mode = document.querySelector('input[name="auth-mode"]:checked');
  const keyGroup = document.getElementById('api-key-group');
  if (keyGroup) keyGroup.hidden = !mode || mode.value !== 'api_key';
}

async function saveSettings() {
  const provider = document.getElementById('provider').value;
  const keyInput = document.getElementById('api-key');
  _pendingKeys[provider] = keyInput.value;
  const apiKeys = Object.fromEntries(
    Object.entries(_pendingKeys)
      .map(([n, k]) => [n, k.trim()])
      .filter(([, k]) => k)
  );
  const payload = {
    provider,
    model: (document.getElementById('model') || {}).value || '',
    auth_mode: (document.querySelector('input[name="auth-mode"]:checked') || {}).value || 'api_key',
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
    _savedKeys = data.saved_keys;
    _pendingKeys = {};
    keyInput.value = '';
    updateProviderFields();
    showToast('Settings saved!', 'success');
  } catch (e) {
    showToast(e.message, 'error');
  }
}

async function testProvider() {
  const btn = document.getElementById('test-provider-btn');
  if (btn) { btn.disabled = true; btn.classList.add('testing'); }
  try {
    const res = await fetch('/api/test-provider', { method: 'POST' });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || `Error ${res.status}`);
    showToast(data.message, 'success');
  } catch (e) {
    showToast(e.message, 'error');
  } finally {
    if (btn) { btn.disabled = false; btn.classList.remove('testing'); }
  }
}

document.addEventListener('DOMContentLoaded', function() {
  initSettings();
});

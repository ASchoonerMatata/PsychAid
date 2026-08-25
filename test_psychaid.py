import io
import json
import os
import re
import urllib.error
from pathlib import Path

import pytest

import report_generator
import app as app_module
from app import _sanitize_download_name, app
from pdf_forms import get_pdf_bytes
from providers import PROVIDERS, ProviderError, _gemini_generate, resolve_provider
from report_generator import _normalise_config, extract_text, load_config, report_to_docx, save_config


def _sentinel_credential():
    return "unit-test-" + "credential"


def test_normalise_config_migrates_bare_legacy_key():
    cfg = _normalise_config({"api_key": "x"})

    assert cfg["provider"] == "anthropic"
    assert cfg["api_keys"]["anthropic"] == "x"


def test_normalise_config_preserves_existing_keys_over_legacy_key():
    cfg = _normalise_config({
        "api_key": "legacy",
        "api_keys": {"anthropic": "current", "gemini": "gemini-current"},
    })

    assert cfg["api_keys"] == {
        "anthropic": "current",
        "gemini": "gemini-current",
    }


@pytest.mark.parametrize(
    "garbage",
    [
        None,
        [],
        {
            "provider": 1,
            "model": [],
            "auth_mode": object(),
            "api_key": 2,
            "api_keys": {3: 4, "anthropic": 5},
        },
    ],
)
def test_normalise_config_accepts_garbage_without_raising(garbage):
    assert _normalise_config(garbage) == {
        "provider": "anthropic",
        "model": "",
        "auth_mode": "api_key",
        "api_keys": {},
    }


def test_normalise_config_invalid_auth_mode_falls_back_to_api_key():
    assert _normalise_config({"auth_mode": "invalid"})["auth_mode"] == "api_key"


def test_resolve_provider_rejects_unknown_provider():
    with pytest.raises(ProviderError, match="Unknown AI provider: missing"):
        resolve_provider({"provider": "missing"})


def test_resolve_provider_requires_provider_api_key():
    with pytest.raises(ProviderError, match="Anthropic"):
        resolve_provider({
            "provider": "anthropic",
            "auth_mode": "api_key",
            "api_keys": {},
        })


def test_resolve_provider_names_missing_subscription_environment_variable(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    with pytest.raises(ProviderError, match="GEMINI_API_KEY"):
        resolve_provider({"provider": "gemini", "auth_mode": "subscription"})


def test_resolve_provider_uses_subscription_environment_variable(monkeypatch):
    credential = _sentinel_credential()
    monkeypatch.setenv("GEMINI_API_KEY", credential)

    _, resolved_credential, _ = resolve_provider({
        "provider": "gemini",
        "auth_mode": "subscription",
    })

    assert resolved_credential == credential


@pytest.mark.parametrize(
    ("override", "expected"),
    [
        ("custom-model", "custom-model"),
        ("   ", PROVIDERS["gemini"]["default_model"]),
    ],
)
def test_resolve_provider_model_override_or_default(override, expected):
    _, _, model = resolve_provider({
        "provider": "gemini",
        "auth_mode": "api_key",
        "api_keys": {"gemini": _sentinel_credential()},
        "model": override,
    })

    assert model == expected


class _UrlopenResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_gemini_response_joins_text_parts(monkeypatch):
    payload = {
        "candidates": [{"content": {"parts": [{"text": "Hello "}, {"text": "world"}]}}]
    }
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda request, timeout: _UrlopenResponse(payload),
    )

    assert _gemini_generate("system", "user", _sentinel_credential(), "model") == "Hello world"


def test_gemini_response_ignores_non_text_thought_parts(monkeypatch):
    payload = {
        "candidates": [{
            "content": {
                "parts": [
                    {"thoughtSignature": "opaque"},
                    {"text": "Visible"},
                    {"inlineData": {"mimeType": "application/octet-stream"}},
                    {"text": " text"},
                ]
            }
        }]
    }
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda request, timeout: _UrlopenResponse(payload),
    )

    assert _gemini_generate("system", "user", _sentinel_credential(), "model") == "Visible text"


def test_gemini_http_error_uses_api_message_and_redacts_key(monkeypatch):
    credential = _sentinel_credential()
    body = json.dumps({
        "error": {"message": f"Credential rejected: {credential}"}
    }).encode("utf-8")
    error = urllib.error.HTTPError(
        "https://example.invalid",
        400,
        "Bad Request",
        {},
        io.BytesIO(body),
    )

    def raise_http_error(request, timeout):
        raise error

    monkeypatch.setattr("urllib.request.urlopen", raise_http_error)

    with pytest.raises(ProviderError) as raised:
        _gemini_generate("system", "user", credential, "model")

    assert "Credential rejected" in str(raised.value)
    assert credential not in str(raised.value)


def test_gemini_blocked_response_names_reason(monkeypatch):
    payload = {"promptFeedback": {"blockReason": "SAFETY"}}
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda request, timeout: _UrlopenResponse(payload),
    )

    with pytest.raises(ProviderError, match="SAFETY"):
        _gemini_generate("system", "user", _sentinel_credential(), "model")


def test_extract_text_txt_round_trips():
    text = "A deterministic text file."

    assert extract_text(text.encode("utf-8"), "notes.txt") == text


def test_extract_text_unknown_extension_replaces_invalid_utf8():
    assert extract_text(b"valid\xfftail", "notes.unknown") == "valid\ufffdtail"


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits only")
def test_save_config_writes_private_file(tmp_path, monkeypatch):
    config_path = tmp_path / "PsychAid" / "config.json"
    monkeypatch.setattr(report_generator, "_config_path", lambda: str(config_path))

    save_config({"provider": "anthropic"})

    assert config_path.parent.stat().st_mode & 0o777 == 0o700
    assert config_path.stat().st_mode & 0o777 == 0o600

    config_path.chmod(0o644)
    save_config({"provider": "gemini"})

    assert config_path.stat().st_mode & 0o777 == 0o600


def test_report_to_docx_returns_zip_and_numbered_line_is_heading():
    from docx import Document

    docx_bytes = report_to_docx("1. Identifying Information\nBody text", "Test Client")
    document = Document(io.BytesIO(docx_bytes))
    numbered_line = next(
        paragraph for paragraph in document.paragraphs
        if paragraph.text == "1. Identifying Information"
    )

    assert docx_bytes.startswith(b"PK")
    assert numbered_line.style.name == "Heading 1"


@pytest.fixture
def client(tmp_path, monkeypatch):
    config_path = tmp_path / "PsychAid" / "config.json"
    monkeypatch.setattr(report_generator, "_config_path", lambda: str(config_path))
    app.config.update(TESTING=True)
    with app.test_client() as test_client:
        yield test_client


def test_page_routes_return_success(client):
    assert client.get("/").status_code == 200
    assert client.get("/settings").status_code == 200


def test_settings_page_never_renders_saved_key(client):
    credential = _sentinel_credential()
    response = client.post("/api/save-settings", json={
        "provider": "anthropic",
        "auth_mode": "api_key",
        "api_key": credential,
    })

    assert response.status_code == 200
    assert credential.encode("utf-8") not in client.get("/settings").data


@pytest.mark.parametrize(
    "payload",
    [
        {"provider": "unknown", "auth_mode": "api_key"},
        {"provider": "anthropic", "auth_mode": "unknown"},
    ],
)
def test_save_settings_rejects_unknown_provider_or_auth_mode(client, payload):
    assert client.post("/api/save-settings", json=payload).status_code == 400


def test_save_settings_empty_key_preserves_existing_key(client):
    credential = _sentinel_credential()
    base_payload = {"provider": "anthropic", "auth_mode": "api_key"}
    assert client.post(
        "/api/save-settings",
        json={**base_payload, "api_key": credential},
    ).status_code == 200

    assert client.post(
        "/api/save-settings",
        json={**base_payload, "api_key": ""},
    ).status_code == 200

    assert load_config()["api_keys"]["anthropic"] == credential


def test_generate_report_requires_files(client):
    assert client.post("/api/generate-report").status_code == 400


def test_generate_report_rejects_more_than_twenty_files(client):
    files = [(io.BytesIO(b"text"), f"notes-{i}.txt") for i in range(21)]

    response = client.post(
        "/api/generate-report",
        data={"files": files},
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "No more than 20 files may be uploaded."}


@pytest.mark.parametrize("filename", ["legacy.doc", "script.html", "no-extension"])
def test_generate_report_rejects_unsupported_extension(client, filename):
    response = client.post(
        "/api/generate-report",
        data={"files": (io.BytesIO(b"content"), filename)},
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert filename in response.get_json()["error"]
    assert ".pdf, .docx, .txt" in response.get_json()["error"]


def test_generate_report_rejects_request_over_25_mb(client):
    response = client.post(
        "/api/generate-report",
        data=b"x" * (25 * 1024 * 1024 + 1),
        content_type="application/octet-stream",
    )

    assert response.status_code == 413
    assert response.get_json() == {
        "error": "Uploaded files are too large (25 MB limit)."
    }


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (" Jane  Doe ", "Jane_Doe"),
        ("../Jane\\Doe\n", "..JaneDoe"),
        ("\x00\r\n/\\", "Client"),
        ("x" * 81, "x" * 80),
    ],
)
def test_sanitize_download_name(value, expected):
    assert _sanitize_download_name(value) == expected


def test_generate_report_sanitizes_download_filename(client, monkeypatch):
    monkeypatch.setattr(app_module, "generate_report", lambda files, cfg: "Report")
    monkeypatch.setattr(app_module, "report_to_docx", lambda text, name: b"document")

    response = client.post(
        "/api/generate-report",
        data={
            "files": (io.BytesIO(b"content"), "notes.txt"),
            "client_name": "Jane\n/ Doe",
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert "Jane_Doe_Report.docx" in response.headers["Content-Disposition"]


def test_upload_list_renders_filename_as_text():
    source = (Path(__file__).parent / "static" / "app.js").read_text(encoding="utf-8")
    render = source.split("function renderFileList()", 1)[1].split("\n}\n", 1)[0]

    assert "innerHTML" not in render
    assert "name.textContent = f.name" in render
    assert "replaceChildren()" in render
    assert "addEventListener('click'" in render


def test_download_form_returns_pdf_or_404(client):
    response = client.get("/api/download-form/gad7/self?name=Jane%0A%2F%20Doe")

    assert response.status_code == 200
    assert response.data.startswith(b"%PDF")
    assert "Jane_Doe_GAD-7_Self.pdf" in response.headers["Content-Disposition"]
    assert client.get("/api/download-form/not-a-scale/not-a-rater").status_code == 404


def test_every_form_advertised_by_ui_generates_a_pdf():
    template = (Path(__file__).parent / "templates" / "assessment.html").read_text(
        encoding="utf-8"
    )
    pairs = re.findall(r"downloadForm\('([^']+)'\s*,\s*'([^']+)'\)", template)

    assert pairs, "No downloadable assessment forms were found in the UI template."
    for scale, rater in pairs:
        pdf_bytes = get_pdf_bytes(scale, rater, client_name="Test Client")
        assert pdf_bytes is not None, f"No PDF generator for UI form {scale}/{rater}"
        assert pdf_bytes.startswith(b"%PDF"), f"Invalid PDF for UI form {scale}/{rater}"


def _live_credential_or_skip(request, variable):
    if request.config.option.markexpr.strip() != "live":
        pytest.skip("live tests are opt-in; run with -m live")
    credential = os.environ.get(variable)
    if not credential:
        pytest.skip(f"{variable} is not set")
    return credential


@pytest.mark.live
def test_live_gemini_generate_content_round_trip(request):
    _live_credential_or_skip(request, "GEMINI_API_KEY")

    provider, api_key, model = resolve_provider({
        "provider": "gemini",
        "auth_mode": "subscription",
    })
    result = provider["generate"](
        "Reply briefly and plainly.",
        "Reply with only OK.",
        api_key,
        model,
    )

    assert isinstance(result, str)
    assert result.strip()


@pytest.mark.live
def test_live_anthropic_generate_content_round_trip(request):
    _live_credential_or_skip(request, "ANTHROPIC_API_KEY")

    provider, api_key, model = resolve_provider({
        "provider": "anthropic",
        "auth_mode": "subscription",
    })
    result = provider["generate"](
        "Reply briefly and plainly.",
        "Reply with only OK.",
        api_key,
        model,
    )

    assert isinstance(result, str)
    assert result.strip()

import json
import os
import urllib.error
import urllib.parse
import urllib.request


class ProviderError(Exception):
    pass


def _safe_error_message(error, api_key=None):
    message = str(error).strip() or error.__class__.__name__
    if api_key:
        message = message.replace(api_key, '[redacted]')
    return message


def _anthropic_generate(
    system_prompt: str,
    user_text: str,
    api_key: str | None,
    model: str
) -> str:
    if not api_key:
        raise ProviderError('Anthropic credential is missing.')

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=8000,
            system=system_prompt,
            messages=[{'role': 'user', 'content': user_text}]
        )
    except Exception as error:
        status = getattr(error, 'status_code', None)
        detail = _safe_error_message(error, api_key)
        prefix = f'Anthropic request failed (HTTP {status})' if status else 'Anthropic request failed'
        raise ProviderError(f'{prefix}: {detail}') from None

    try:
        text = ''.join(
            block.text for block in response.content
            if getattr(block, 'text', None)
        ).strip()
    except (AttributeError, TypeError):
        text = ''
    if not text:
        raise ProviderError('Anthropic returned an empty response.')
    return text


def _gemini_generate(
    system_prompt: str,
    user_text: str,
    api_key: str | None,
    model: str
) -> str:
    if not api_key:
        raise ProviderError('Google Gemini credential is missing.')

    encoded_model = urllib.parse.quote(model, safe='')
    url = (
        'https://generativelanguage.googleapis.com/v1beta/models/'
        f'{encoded_model}:generateContent'
    )
    payload = json.dumps({
        'contents': [{'parts': [{'text': user_text}]}],
        'systemInstruction': {'parts': [{'text': system_prompt}]}
    }).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            'Content-Type': 'application/json',
            'x-goog-api-key': api_key
        },
        method='POST'
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            data = json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as error:
        detail = error.reason or 'request rejected'
        try:
            body = json.loads(error.read().decode('utf-8'))
            if isinstance(body, dict):
                error_data = body.get('error') or {}
                if isinstance(error_data, dict):
                    detail = error_data.get('message') or detail
        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
            pass
        detail = _safe_error_message(detail, api_key)
        raise ProviderError(
            f'Google Gemini request failed (HTTP {error.code}): {detail}'
        ) from None
    except urllib.error.URLError as error:
        detail = _safe_error_message(error.reason, api_key)
        raise ProviderError(f'Google Gemini request failed: {detail}') from None
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ProviderError('Google Gemini returned an unreadable response.') from None

    try:
        candidates = data.get('candidates') or []
        parts = candidates[0].get('content', {}).get('parts', []) if candidates else []
        text = ''.join(
            part['text'] for part in parts
            if isinstance(part, dict) and isinstance(part.get('text'), str)
        ).strip()
    except (AttributeError, IndexError, TypeError):
        text = ''
    if text:
        return text

    feedback = data.get('promptFeedback') if isinstance(data, dict) else {}
    blocked = feedback.get('blockReason') if isinstance(feedback, dict) else None
    if blocked:
        raise ProviderError(f'Google Gemini blocked the response: {blocked}.')
    raise ProviderError('Google Gemini returned an empty response.')


PROVIDERS = {
    'anthropic': {
        'label': 'Anthropic',
        'default_model': 'claude-opus-4-5',
        'models': ['claude-opus-4-5'],
        'auth_env': 'ANTHROPIC_API_KEY',
        'docs_url': 'https://console.anthropic.com/',
        'generate': _anthropic_generate
    },
    'gemini': {
        'label': 'Google Gemini',
        'default_model': 'gemini-flash-latest',
        'models': ['gemini-flash-latest'],
        'auth_env': 'GEMINI_API_KEY',
        'docs_url': 'https://aistudio.google.com/app/apikey',
        'generate': _gemini_generate
    }
}


def resolve_provider(cfg):
    provider_name = cfg.get('provider') or 'anthropic'
    provider = PROVIDERS.get(provider_name)
    if not provider:
        raise ProviderError(f'Unknown AI provider: {provider_name}.')

    configured_model = cfg.get('model')
    model = configured_model.strip() if isinstance(configured_model, str) else ''
    model = model or provider['default_model']
    auth_mode = cfg.get('auth_mode') or 'api_key'
    if auth_mode == 'api_key':
        api_keys = cfg.get('api_keys') if isinstance(cfg.get('api_keys'), dict) else {}
        configured_key = api_keys.get(provider_name)
        api_key = configured_key.strip() if isinstance(configured_key, str) else ''
        if not api_key:
            raise ProviderError(
                f'No {provider["label"]} API key is saved. Add one in Settings.'
            )
    elif auth_mode == 'subscription':
        api_key = os.environ.get(provider['auth_env'], '').strip()
        if not api_key:
            raise ProviderError(
                f'{provider["label"]} environment credential is unavailable. '
                f'Set {provider["auth_env"]} and restart PsychAid.'
            )
    else:
        raise ProviderError(f'Unknown authentication mode: {auth_mode}.')

    return provider, api_key, model

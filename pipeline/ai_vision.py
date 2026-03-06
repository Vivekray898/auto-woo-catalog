from __future__ import annotations

import base64
import mimetypes
from pathlib import Path

import google.generativeai as genai
import requests
from PIL import Image
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from config import Settings
from logger import get_logger
from utils import (
    PipelineError,
    dump_json,
    extract_json_object,
    sleep_between_ai_requests,
    validate_ai_payload,
)

logger = get_logger()

VISION_PROMPT = """
Du bist ein E-Commerce-Katalogexperte fuer deutsche WooCommerce-Shops.
Analysiere das Produktbild und erstelle verkaufsstarke, SEO-optimierte Katalogdaten.
Antworte AUSSCHLIESSLICH mit gueltigem JSON in diesem exakten Format:
{
  "title": "",
  "short_description": "",
  "long_description": "",
  "features": [],
  "tags": [],
  "category": ""
}
Regeln:
- title: klar, kaufmaennisch, maximal 80 Zeichen.
- short_description: 1 bis 2 Saetze fuer eine Produktkurzbeschreibung.
- long_description: SEO-optimierter Fliesstext fuer WooCommerce in deutscher Sprache.
- features: 3 bis 6 kurze Bullet-Points als Array.
- tags: 4 bis 8 relevante, kurze Keywords als Array.
- category: genau eine moeglichst passende Shop-Kategorie.
- Keine Markdown-Codebloecke.
- Keine Erklaerungen ausserhalb des JSON.
""".strip()

REQUIRED_AI_FIELDS = (
    "title",
    "short_description",
    "long_description",
    "features",
    "category",
    "tags",
)

GROQ_CHAT_COMPLETIONS_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
CEREBRAS_CHAT_COMPLETIONS_ENDPOINT = "https://api.cerebras.ai/v1/chat/completions"


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((PipelineError, requests.RequestException, Exception)),
)
def analyze_with_fallback(image_path: str | Path, settings: Settings) -> str:
    """Try configured AI provider and fall back to available ones on failure."""
    order = settings.ai_providers.copy()
    start = settings.ai_provider.lower()
    if start in order:
        order.remove(start)
    order.insert(0, start)

    last_exc: Exception | None = None
    for provider in order:
        try:
            logger.info("Attempting provider '%s'", provider)
            if provider == "gemini":
                return _call_gemini(image_path, settings)
            elif provider in ("groq", "cerebras"):
                api_key = settings.groq_api_key if provider == "groq" else settings.cerebras_api_key
                model = settings.groq_model if provider == "groq" else settings.cerebras_model
                endpoint = GROQ_CHAT_COMPLETIONS_ENDPOINT if provider == "groq" else CEREBRAS_CHAT_COMPLETIONS_ENDPOINT
                label = provider.capitalize()
                return _call_openai_compatible(
                    image_path=image_path,
                    api_key=api_key,
                    model=model,
                    endpoint=endpoint,
                    provider_label=label,
                    settings=settings,
                )
            else:
                raise PipelineError(f"Unknown AI provider listed: {provider}")
        except Exception as exc:
            logger.warning("AI provider %s failed: %s", provider, exc)
            last_exc = exc
            continue
    raise PipelineError("All AI providers failed.") from last_exc


def analyze_product_image(image_path: str | Path, settings: Settings) -> dict:
    """Analyze a product image and return normalized catalog fields, using failover."""
    response_text = analyze_with_fallback(image_path, settings)
    payload = extract_json_object(response_text, required_fields=REQUIRED_AI_FIELDS)
    normalized = validate_ai_payload(payload)
    logger.info("AI output: %s", dump_json(normalized))
    return normalized


def _call_gemini(image_path: str | Path, settings: Settings) -> str:
    """Send an image to Gemini Vision and return the raw response text."""
    sleep_between_ai_requests(settings.ai_request_delay_seconds)
    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel(settings.gemini_model)

    with Image.open(image_path) as image:
        response = model.generate_content([VISION_PROMPT, image.copy()])

    try:
        response_text = getattr(response, "text", "") or ""
    except Exception as exc:  # noqa: BLE001 - blocked model responses should be retried.
        raise PipelineError("Gemini response was blocked or unreadable.") from exc

    if not response_text.strip():
        raise PipelineError("Gemini returned an empty response.")
    return response_text


def _call_openai_compatible(
    image_path: str | Path,
    api_key: str,
    model: str,
    endpoint: str,
    provider_label: str,
    settings: Settings,
) -> str:
    """Send a multimodal chat completion request to an OpenAI-compatible AI endpoint."""
    sleep_between_ai_requests(settings.ai_request_delay_seconds)
    data_url = _image_to_data_url(image_path)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "temperature": 0.2,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": VISION_PROMPT},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
    }

    response = requests.post(
        endpoint,
        headers=headers,
        json=payload,
        timeout=settings.request_timeout,
    )
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise PipelineError(
            f"{provider_label} AI request failed with status {response.status_code}: {response.text}"
        ) from exc

    response_payload = response.json()
    response_text = _extract_openai_content(response_payload)
    if not response_text.strip():
        raise PipelineError(f"{provider_label} returned an empty response.")
    return response_text


def _image_to_data_url(image_path: str | Path) -> str:
    """Encode a local image as a data URL for OpenAI-compatible vision APIs."""
    path = Path(image_path)
    mime_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _extract_openai_content(payload: dict) -> str:
    """Extract text content from OpenAI-compatible chat completion responses."""
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise PipelineError("AI provider response did not include any choices.")

    message = choices[0].get("message", {})
    content = message.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
        return "\n".join(part for part in parts if part)
    return str(content or "")

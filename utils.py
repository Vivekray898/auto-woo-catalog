from __future__ import annotations

import csv
import json
import re
import time
import unicodedata
from pathlib import Path
from typing import Iterable


class PipelineError(RuntimeError):
    """Raised when a pipeline step fails in a recoverable way."""


def ensure_directory(path: Path) -> Path:
    """Create a directory tree if it does not exist and return the path."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def sanitize_filename(value: str) -> str:
    """Convert arbitrary text into a filesystem-safe ASCII filename."""
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", normalized).strip("-._")
    return cleaned or "image"


def strip_code_fence(text: str) -> str:
    """Remove markdown code fences if the AI wraps the JSON response."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```[A-Za-z0-9_-]*", "", stripped).strip()
        stripped = re.sub(r"```$", "", stripped).strip()
    return stripped


def _extract_fenced_json_candidates(text: str) -> list[str]:
    """Extract JSON candidates from fenced markdown blocks first."""
    matches = re.findall(r"```(?:json)?\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
    return [match.strip() for match in matches if match.strip()]


def _extract_braced_json_candidates(text: str) -> list[str]:
    """Extract balanced JSON object candidates from arbitrary model output."""
    candidates: list[str] = []
    depth = 0
    start_index: int | None = None
    in_string = False
    escape_next = False

    for index, char in enumerate(text):
        if in_string:
            if escape_next:
                escape_next = False
            elif char == "\\":
                escape_next = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue

        if char == "{":
            if depth == 0:
                start_index = index
            depth += 1
        elif char == "}" and depth > 0:
            depth -= 1
            if depth == 0 and start_index is not None:
                candidates.append(text[start_index : index + 1])
                start_index = None

    return candidates


def extract_json_object(text: str, required_fields: Iterable[str] | None = None) -> dict:
    """Extract and validate the first usable JSON object from a raw AI response string."""
    stripped = text.strip()
    candidates: list[str] = []
    candidates.extend(_extract_fenced_json_candidates(stripped))
    candidates.append(strip_code_fence(stripped))
    candidates.extend(_extract_braced_json_candidates(stripped))

    seen: set[str] = set()
    last_error: PipelineError | None = None
    required = tuple(required_fields or ())

    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue

        if not isinstance(payload, dict):
            last_error = PipelineError("AI response JSON must be an object.")
            continue

        missing = [field for field in required if field not in payload]
        if missing:
            last_error = PipelineError(
                f"AI response JSON is missing required fields: {', '.join(missing)}"
            )
            continue

        return payload

    if last_error is not None:
        raise last_error
    raise PipelineError("AI response did not contain a valid JSON object.")


def validate_ai_payload(payload: dict) -> dict:
    """Normalize and validate the shared AI payload schema used by all providers."""
    if not isinstance(payload, dict):
        raise PipelineError("AI response must be a JSON object.")

    normalized = {
        "title": str(payload.get("title", "")).strip(),
        "short_description": str(payload.get("short_description", "")).strip(),
        "long_description": str(payload.get("long_description", "")).strip(),
        "features": normalize_text_list(payload.get("features", [])),
        "tags": normalize_text_list(payload.get("tags", [])),
        "category": str(payload.get("category", "")).strip(),
    }

    required_fields = ("title", "short_description", "long_description", "category")
    missing = [field for field in required_fields if not normalized[field]]
    if missing:
        raise PipelineError(f"AI response is missing required fields: {', '.join(missing)}")
    if not normalized["features"]:
        raise PipelineError("AI response did not include any product features.")
    if not normalized["tags"]:
        raise PipelineError("AI response did not include any product tags.")
    return normalized


def normalize_text_list(values: object) -> list[str]:
    """Keep only non-empty strings from a list-like AI field."""
    if not isinstance(values, list):
        return []

    normalized: list[str] = []
    for value in values:
        if isinstance(value, str) and value.strip():
            normalized.append(value.strip())
    return normalized


def normalize_category_key(value: str) -> str:
    """Normalize category names so German umlauts and punctuation compare reliably."""
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    normalized = normalized.casefold().strip()
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def deduplicate(values: Iterable[str]) -> list[str]:
    """Deduplicate input URLs while preserving the original order."""
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = value.strip()
        if item and item not in seen:
            result.append(item)
            seen.add(item)
    return result


def load_urls_from_text_file(file_path: str | Path) -> list[str]:
    """Load one image URL per line from a plain text file."""
    path = Path(file_path)
    if not path.exists():
        raise PipelineError(f"Input file does not exist: {path}")

    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
    urls = [line for line in lines if line and not line.startswith("#")]
    return deduplicate(urls)


def load_urls_from_csv(file_path: str | Path) -> list[str]:
    """Load image URLs from a CSV file using common ecommerce column names."""
    path = Path(file_path)
    if not path.exists():
        raise PipelineError(f"CSV file does not exist: {path}")

    urls: list[str] = []
    with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        for row_number, row in enumerate(reader, start=2):
            image_url = ""
            for key in ("image_url", "url", "image", "image_link"):
                image_url = (row.get(key) or "").strip()
                if image_url:
                    break
            if not image_url:
                continue
            urls.append(image_url)

    if not urls:
        raise PipelineError("CSV input did not contain any supported image URL columns.")
    return deduplicate(urls)


def build_feature_html(features: list[str]) -> str:
    """Render AI-generated features as a short HTML bullet list for WooCommerce."""
    if not features:
        return ""
    items = "".join(f"<li>{feature}</li>" for feature in features)
    return f"<ul>{items}</ul>"


def truncate_text(value: str, limit: int) -> str:
    """Trim long text safely for SEO fields without breaking words too aggressively."""
    if len(value) <= limit:
        return value
    shortened = value[: limit - 1].rsplit(" ", 1)[0].strip()
    return (shortened or value[: limit - 1]).strip() + "…"


def dump_json(value: object) -> str:
    """Serialize objects for readable structured logging."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def sleep_between_requests(seconds: float | int | None = None) -> None:
    """Sleep briefly between non-AI API requests to reduce rate-limit pressure."""
    delay = max(0.0, float(seconds or 0))
    if delay > 0:
        time.sleep(delay)


def sleep_between_ai_requests(seconds: float | int | None = None) -> None:
    """Sleep briefly before AI requests to reduce provider throttling."""
    delay = max(0.0, float(seconds or 0))
    if delay > 0:
        time.sleep(delay)

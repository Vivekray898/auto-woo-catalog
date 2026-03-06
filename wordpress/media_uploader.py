from __future__ import annotations

import mimetypes
from pathlib import Path

import requests
from requests.auth import HTTPBasicAuth
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from config import Settings
from logger import get_logger, safe_extra
from utils import PipelineError

logger = get_logger()


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((requests.RequestException, PipelineError)),
)
def upload_media(image_path: str | Path, seo_alt_text: str, settings: Settings) -> int:
    """Upload an image to WordPress media library and return the media ID."""
    path = Path(image_path)
    if not path.exists():
        raise PipelineError(f"Image file does not exist: {path}")

    mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    auth = HTTPBasicAuth(settings.wp_username, settings.wp_app_password)

    logger.info(
        "Uploading image to WordPress: %s",
        path.name,
        extra=safe_extra({"image_url": path.name}),
    )
    with path.open("rb") as image_file:
        response = requests.post(
            settings.wordpress_media_endpoint,
            auth=auth,
            timeout=settings.request_timeout,
            files={"file": (path.name, image_file, mime_type)},
            data={
                "title": path.stem,
                "alt_text": seo_alt_text,
            },
        )

    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise PipelineError(
            f"WordPress media upload failed with status {response.status_code}: {response.text}"
        ) from exc

    payload = response.json()
    media_id = payload.get("id")
    if not isinstance(media_id, int):
        raise PipelineError("WordPress media response did not include a valid media ID.")

    logger.info(
        "WordPress upload succeeded with media_id=%s",
        media_id,
        extra=safe_extra({"image_url": path.name, "outcome": "success"}),
    )
    return media_id

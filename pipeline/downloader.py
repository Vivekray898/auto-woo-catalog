from __future__ import annotations

import mimetypes
from pathlib import Path
from urllib.parse import urlparse

import requests
from PIL import Image, UnidentifiedImageError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from config import Settings
from logger import get_logger
from utils import PipelineError, ensure_directory, sanitize_filename

logger = get_logger()


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type((requests.RequestException, PipelineError)),
)
def download_image(url: str, settings: Settings) -> Path:
    """Download, validate, and persist a product image locally."""
    logger.info("Downloading image from %s", url)
    ensure_directory(settings.downloads_dir)

    response = requests.get(url, timeout=settings.request_timeout, stream=True)
    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "").split(";")[0].strip()
    extension = mimetypes.guess_extension(content_type) if content_type else None
    if not extension:
        extension = Path(urlparse(url).path).suffix or ".jpg"

    file_stem = sanitize_filename(Path(urlparse(url).path).stem or "product-image")
    target_path = settings.downloads_dir / f"{file_stem}{extension}"

    with target_path.open("wb") as output_file:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                output_file.write(chunk)

    try:
        with Image.open(target_path) as image:
            image.verify()
    except (UnidentifiedImageError, OSError) as exc:
        target_path.unlink(missing_ok=True)
        raise PipelineError(f"Downloaded file is not a valid image: {url}") from exc

    logger.info("Saved validated image to %s", target_path)
    return target_path

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from config import ConfigError, get_settings
from logger import build_log_extra, get_logger, safe_extra
from pipeline.ai_vision import analyze_product_image
from pipeline.category_mapper import CategoryMapper
from pipeline.downloader import download_image
from pipeline.seo_generator import generate_seo_fields
from utils import PipelineError, deduplicate, load_urls_from_csv, load_urls_from_text_file
from wordpress.media_uploader import upload_media
from woocommerce.product_creator import create_product

logger = get_logger()


@dataclass
class BatchResult:
    processed: int = 0
    created: int = 0
    failed: int = 0


def parse_args() -> argparse.Namespace:
    """Parse all supported input methods for the catalog pipeline."""
    parser = argparse.ArgumentParser(
        description="Create WooCommerce catalog products automatically from image URLs."
    )
    parser.add_argument("image_urls", nargs="*", help="Direct product image URLs.")
    parser.add_argument("--input-file", help="Text file with one image URL per line.")
    parser.add_argument("--csv", help="CSV file containing image URLs.")
    parser.add_argument("--r2", action="store_true", help="Automatically fetch image URLs from configured Cloudflare R2 bucket.")
    return parser.parse_args()


def collect_image_urls(args: argparse.Namespace, settings) -> list[str]:
    """Merge URLs from various sources into one deduplicated list.

    If --r2 is set, list from R2 bucket instead of other inputs.
    """
    if args.r2:
        from pipeline.r2_reader import list_r2_images

        urls = list_r2_images(settings)
        if not urls:
            logger.warning("R2 bucket contained no image URLs.", extra=safe_extra())
        return deduplicate(urls)

    image_urls = list(args.image_urls)
    if args.input_file:
        image_urls.extend(load_urls_from_text_file(args.input_file))
    if args.csv:
        image_urls.extend(load_urls_from_csv(args.csv))

    urls = deduplicate(image_urls)
    if not urls:
        raise PipelineError("No image URLs supplied. Use CLI args, --input-file, --csv, or --r2.")
    return urls


def process_url(image_url: str, category_mapper: CategoryMapper, settings) -> dict:
    """Run the complete catalog creation pipeline for a single image URL."""
    local_image = download_image(image_url, settings)
    product_data = analyze_product_image(local_image, settings)
    category_name, category_id = category_mapper.resolve(product_data.get("category", ""))
    seo_fields = generate_seo_fields(product_data, category_name)
    logger.info(
        "AI product data prepared",
        extra=build_log_extra(
            product_title=product_data.get("title"),
            image_url=image_url,
            category_id=category_id,
            outcome="success",
        ),
    )
    media_id = upload_media(local_image, seo_fields["image_alt_text"], settings)
    logger.info(
        "WordPress media upload completed",
        extra=build_log_extra(
            product_title=product_data.get("title"),
            image_url=image_url,
            category_id=category_id,
            outcome="success",
        ),
    )
    product = create_product(product_data, media_id, category_id, seo_fields, settings)
    _cleanup_downloaded_image(local_image)
    return product


def _cleanup_downloaded_image(local_image: str | Path) -> None:
    """Delete a successfully processed local image to prevent disk growth over time."""
    image_path = Path(local_image)
    if not image_path.exists():
        return
    try:
        image_path.unlink()
    except OSError as exc:
        logger.warning("Failed to delete local image %s: %s", image_path, exc, extra=safe_extra())


def main() -> int:
    """Process the requested batch and keep going when individual items fail."""
    args = parse_args()
    try:
        settings = get_settings()
        category_mapper = CategoryMapper(settings)
        # collect_image_urls requires the current settings for R2 lookup
        image_urls = collect_image_urls(args, settings)
    except (ConfigError, PipelineError) as exc:
        logger.error(str(exc), extra=safe_extra())
        return 1

    result = BatchResult()
    logger.info("Starting batch for %s image URLs", len(image_urls), extra=safe_extra())

    for index, image_url in enumerate(image_urls, start=1):
        result.processed += 1
        logger.info(
            "[%s/%s] Processing image URL",
            index,
            len(image_urls),
            extra=safe_extra(build_log_extra(image_url=image_url, outcome="started")),
        )
        try:
            product = process_url(image_url, category_mapper, settings)
        except (PipelineError, ConfigError, ValueError) as exc:
            result.failed += 1
            logger.error(
                "Failed to process item: %s",
                exc,
                extra=safe_extra(build_log_extra(image_url=image_url, outcome="failure")),
            )
            continue
        except Exception as exc:  # noqa: BLE001 - unexpected item failures should not kill the batch.
            result.failed += 1
            logger.exception(
                "Unexpected failure while processing item: %s",
                exc,
                extra=safe_extra(build_log_extra(image_url=image_url, outcome="failure")),
            )
            continue

        result.created += 1
        logger.info(
            "Product created successfully: id=%s name=%s permalink=%s",
            product.get("id"),
            product.get("name"),
            product.get("permalink", "n/a"),
            extra=safe_extra(
                build_log_extra(
                    product_title=product.get("name"),
                    image_url=image_url,
                    category_id=(product.get("categories") or [{}])[0].get("id", "-"),
                    outcome="success",
                )
            ),
        )

    logger.info(
        "Batch completed. processed=%s created=%s failed=%s",
        result.processed,
        result.created,
        result.failed,
        extra=safe_extra(),
    )
    return 0 if result.created else 1


if __name__ == "__main__":
    raise SystemExit(main())

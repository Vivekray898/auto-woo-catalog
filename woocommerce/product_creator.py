from __future__ import annotations

import requests
from requests.auth import HTTPBasicAuth
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from config import Settings
from logger import get_logger
from utils import PipelineError, build_feature_html, sleep_between_requests

logger = get_logger()


def build_product_payload(product_data: dict, media_id: int, category_id: int, seo_fields: dict) -> dict:
    """Build the WooCommerce request payload for a draft catalog product."""
    feature_html = build_feature_html(product_data.get("features", []))

    description = f"<p>{product_data['long_description']}</p>"
    if feature_html:
        description += f"<h3>Produktmerkmale</h3>{feature_html}"

    short_description = f"<p>{product_data['short_description']}</p>"
    if feature_html:
        short_description += feature_html

    return {
        "name": product_data["title"],
        "type": "simple",
        "status": "draft",
        "catalog_visibility": "catalog",
        "regular_price": "",
        "manage_stock": False,
        "stock_status": "instock",
        "description": description,
        "short_description": short_description,
        "categories": [{"id": category_id}],
        "tags": [{"name": tag} for tag in product_data.get("tags", [])],
        "images": [{"id": media_id}],
        "meta_data": [
            {"key": "rank_math_title", "value": seo_fields["seo_title"]},
            {"key": "rank_math_description", "value": seo_fields["meta_description"]},
            {"key": "rank_math_focus_keyword", "value": seo_fields["focus_keyword"]},
            {"key": "_auto_woo_seo_title", "value": seo_fields["seo_title"]},
            {"key": "_auto_woo_meta_description", "value": seo_fields["meta_description"]},
            {"key": "_auto_woo_image_alt_text", "value": seo_fields["image_alt_text"]},
        ],
    }


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((requests.RequestException, PipelineError)),
)
def create_product(product_data: dict, media_id: int, category_id: int, seo_fields: dict, settings: Settings) -> dict:
    """Create a WooCommerce draft catalog product and return the API response."""
    payload = build_product_payload(product_data, media_id, category_id, seo_fields)
    auth = HTTPBasicAuth(settings.wc_consumer_key, settings.wc_consumer_secret)

    logger.info("Creating WooCommerce draft product: %s", product_data["title"])
    sleep_between_requests(settings.request_delay_seconds)
    response = requests.post(
        settings.woocommerce_products_endpoint,
        auth=auth,
        timeout=settings.request_timeout,
        json=payload,
    )
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise PipelineError(
            f"WooCommerce product creation failed with status {response.status_code}: {response.text}"
        ) from exc

    result = response.json()
    product_id = result.get("id")
    if not isinstance(product_id, int):
        raise PipelineError("WooCommerce response did not include a valid product ID.")

    logger.info("WooCommerce product created successfully with id=%s", product_id)
    return result

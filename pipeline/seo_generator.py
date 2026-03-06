from __future__ import annotations

from utils import truncate_text


def generate_seo_fields(product_data: dict, mapped_category: str) -> dict:
    """Create German SEO helper fields from the AI-generated product data."""
    title = product_data["title"].strip()
    short_description = product_data["short_description"].strip()
    category = mapped_category.strip() or "Produktkatalog"
    first_feature = product_data.get("features", [""])[0].strip()
    focus_keyword = (product_data.get("tags", [""]) or [""])[0].strip() or title

    seo_title = truncate_text(f"{title} online entdecken | {category.title()}", 65)

    meta_seed = short_description
    if first_feature:
        meta_seed = f"{short_description} Highlight: {first_feature}."
    meta_description = truncate_text(meta_seed, 155)

    image_alt_text = truncate_text(f"{title} aus der Kategorie {category}", 125)

    return {
        "seo_title": seo_title,
        "meta_description": meta_description,
        "focus_keyword": truncate_text(focus_keyword, 70),
        "image_alt_text": image_alt_text,
    }

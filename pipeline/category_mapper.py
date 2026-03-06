from __future__ import annotations

import json
from pathlib import Path

from config import Settings
from logger import get_logger, safe_extra
from utils import normalize_category_key

logger = get_logger()

# These aliases help convert common English or variant AI outputs into store categories.
ALIASES = {
    "uncategorized": "uncategorized",
    "electronics": "elektronik",
    "electronic": "elektronik",
    "electronics accessories": "elektronikartikel",
    "phone accessories": "handy-zubehor",
    "mobile accessories": "handy-zubehor",
    "baumarkt": "baumarkt & werkzeuge",
    "hardware": "baumarkt & werkzeuge",
    "tools": "baumarkt & werkzeuge",
    "home improvement": "baumarkt & werkzeuge",
    "garden": "garten",
    "garden & plants": "garten & pflanzen",
    "garden plants": "garten & pflanzen",
    "garden tools": "gartenwerkzeuge",
    "flowers": "blumen",
    "plants": "zimmerpflanzen",
    "home": "wohnen & haushalt",
    "home & household": "wohnen & haushalt",
    "household": "wohnen & haushalt",
    "home decor": "dekoration",
    "frames": "bilderrahmen",
    "fashion": "mode & accessoires",
    "fashion accessories": "mode & accessoires",
    "belts": "gurtel",
    "bags": "taschen",
    "shoes": "schuhe",
    "health": "gesundheit & drogerie",
    "drugstore": "gesundheit & drogerie",
    "office": "schreibwaren & geschenke",
    "stationery": "schreibwaren & geschenke",
    "gifts": "schreibwaren & geschenke",
    "learning": "lernmaterial",
    "toys": "spielzeug",
    "food": "lebensmittel",
    "travel": "reisebedarf",
    "seasonal": "saisonale artikel",
    "automotive": "automotive",
    "autozubehor": "autozubehor",
    "fahrradzubehor": "fahrradzubehor",
    "zimmerpflanzen": "zimmerpflanzen",
    "gesundheit & drogerie": "gesundheit & drogerie",
    "mode & accessoires": "mode & accessoires",
    "wohnen & haushalt": "wohnen & haushalt",
    "schreibwaren & geschenke": "schreibwaren & geschenke",
}


class CategoryMapper:
    """Load category IDs from JSON and resolve AI category names safely."""

    def __init__(self, settings: Settings) -> None:
        self._mapping = self._load_mapping(settings.category_map_path)
        self.fallback_id = self._mapping.get("uncategorized", ("uncategorized", 15))[1]

    @staticmethod
    def _load_mapping(file_path: str | Path) -> dict[str, tuple[str, int]]:
        path = Path(file_path)
        with path.open("r", encoding="utf-8") as handle:
            raw_mapping = json.load(handle)
        return {
            normalize_category_key(key): (str(key), int(value))
            for key, value in raw_mapping.items()
        }

    def resolve(self, ai_category: str) -> tuple[str, int]:
        """Return the normalized category label and the WooCommerce category ID."""
        normalized = normalize_category_key(ai_category)
        if not normalized:
            logger.warning("AI category missing, using Uncategorized fallback.", extra=safe_extra())
            return "uncategorized", self.fallback_id

        alias_target = ALIASES.get(normalized, normalized)
        if alias_target in self._mapping:
            return self._mapping[alias_target]

        for category_name, category_value in self._mapping.items():
            if alias_target in category_name or category_name in alias_target:
                return category_value

        logger.warning("No category mapping found for '%s', using Uncategorized fallback.", ai_category, extra=safe_extra())
        return "uncategorized", self.fallback_id

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DOWNLOAD_DIR = DATA_DIR / "downloads"
INPUT_DIR = BASE_DIR / "inputs"
LOG_DIR = BASE_DIR / "logs"
CATEGORY_MAP_PATH = DATA_DIR / "category_map.json"

# Load environment variables from the project root so local execution is simple.
load_dotenv(BASE_DIR / ".env")


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str
    groq_api_key: str
    cerebras_api_key: str
    wp_url: str
    wp_username: str
    wp_app_password: str
    wc_consumer_key: str
    wc_consumer_secret: str
    ai_provider: str = "gemini"
    gemini_model: str = "gemini-2.0-flash"
    groq_model: str = "llama-3.2-90b-vision-preview"
    cerebras_model: str = "llama-4-scout-17b-16e-instruct"
    request_timeout: int = 60
    request_delay_seconds: float = 2.0
    ai_request_delay_seconds: float = 3.0
    language: str = "de"
    downloads_dir: Path = DOWNLOAD_DIR
    log_dir: Path = LOG_DIR
    category_map_path: Path = CATEGORY_MAP_PATH

    @property
    def ai_providers(self) -> list[str]:
        """Return the full list of supported AI providers in priority order."""
        return ["gemini", "groq", "cerebras"]

    @property
    def wordpress_media_endpoint(self) -> str:
        return f"{self.wp_url}/wp-json/wp/v2/media"

    @property
    def woocommerce_products_endpoint(self) -> str:
        return f"{self.wp_url}/wp-json/wc/v3/products"


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ConfigError(f"Missing required environment variable: {name}")
    return value


def _optional(name: str) -> str:
    return os.getenv(name, "").strip()


def get_settings() -> Settings:
    """Build the application settings object from environment variables."""
    timeout = os.getenv("REQUEST_TIMEOUT", "60").strip()
    request_delay = os.getenv("REQUEST_DELAY_SECONDS", "2").strip()
    ai_request_delay = os.getenv("AI_REQUEST_DELAY_SECONDS", "3").strip()
    try:
        request_timeout = int(timeout)
    except ValueError as exc:
        raise ConfigError("REQUEST_TIMEOUT must be an integer.") from exc

    try:
        request_delay_seconds = float(request_delay)
        ai_request_delay_seconds = float(ai_request_delay)
    except ValueError as exc:
        raise ConfigError("REQUEST_DELAY_SECONDS and AI_REQUEST_DELAY_SECONDS must be numeric.") from exc

    ai_provider = (os.getenv("AI_PROVIDER", "gemini").strip() or "gemini").lower()
    if ai_provider not in {"gemini", "groq", "cerebras"}:
        raise ConfigError("AI_PROVIDER must be one of: gemini, groq, cerebras.")

    gemini_api_key = _optional("GEMINI_API_KEY")
    groq_api_key = _optional("GROQ_API_KEY")
    cerebras_api_key = _optional("CEREBRAS_API_KEY")

    if ai_provider == "gemini" and not gemini_api_key:
        raise ConfigError("Missing required environment variable: GEMINI_API_KEY")
    if ai_provider == "groq" and not groq_api_key:
        raise ConfigError("Missing required environment variable: GROQ_API_KEY")
    if ai_provider == "cerebras" and not cerebras_api_key:
        raise ConfigError("Missing required environment variable: CEREBRAS_API_KEY")

    return Settings(
        gemini_api_key=gemini_api_key,
        groq_api_key=groq_api_key,
        cerebras_api_key=cerebras_api_key,
        wp_url=_required("WP_URL").rstrip("/"),
        wp_username=_required("WP_USERNAME"),
        wp_app_password=_required("WP_APP_PASSWORD"),
        wc_consumer_key=_required("WC_CONSUMER_KEY"),
        wc_consumer_secret=_required("WC_CONSUMER_SECRET"),
        ai_provider=ai_provider,
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash").strip() or "gemini-2.0-flash",
        groq_model=os.getenv("GROQ_MODEL", "llama-3.2-90b-vision-preview").strip()
        or "llama-3.2-90b-vision-preview",
        cerebras_model=os.getenv("CEREBRAS_MODEL", "llama-4-scout-17b-16e-instruct").strip()
        or "llama-4-scout-17b-16e-instruct",
        request_timeout=request_timeout,
        request_delay_seconds=request_delay_seconds,
        ai_request_delay_seconds=ai_request_delay_seconds,
        language=os.getenv("CONTENT_LANGUAGE", "de").strip() or "de",
        downloads_dir=Path(os.getenv("DOWNLOAD_DIR", str(DOWNLOAD_DIR))),
        log_dir=Path(os.getenv("LOG_DIR", str(LOG_DIR))),
        category_map_path=Path(os.getenv("CATEGORY_MAP_PATH", str(CATEGORY_MAP_PATH))),
    )
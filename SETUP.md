# Auto WooCommerce Catalog Setup

This document explains how to install and run the **auto_woo_catalog** pipeline, which
creates WooCommerce catalogue products from image URLs using AI.

## Prerequisites

* Python 3.11+ (3.12 used during development)
* Git (optional)
* A WooCommerce-enabled WordPress site with REST API credentials
* AI provider API key(s) for one or more of Gemini, Groq, or Cerebras

## Directory structure

```
auto_woo_catalog/
├── config.py
├── logger.py
├── utils.py
├── main.py
├── requirements.txt
├── SETUP.md            # this file
├── .env.example
├── data/
│   └── category_map.json
├── inputs/
│   ├── image_urls.txt
│   └── products.csv
├── pipeline/
│   ├── ai_vision.py
│   ├── category_mapper.py
│   ├── downloader.py
│   └── seo_generator.py
├── wordpress/
│   └── media_uploader.py
├── woocommerce/
│   └── product_creator.py
└── logs/
    └── pipeline.log
```

## Setup steps

1. **Clone or copy the repository** if not already in workspace.

2. **Create a virtual environment and activate it** (Windows PowerShell shown):
   ```powershell
   cd "c:\flutter projects\plugins\auto-woo\auto_woo_catalog"
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   ```

3. **Install dependencies:**
   ```powershell
   pip install -r requirements.txt
   ```

4. **Create and edit the `.env` file** based on `.env.example`:
   ```powershell
   copy .env.example .env
   notepad .env
   ```
   Provide your API keys and site credentials:
   ```env
   AI_PROVIDER=gemini           # or groq, cerebras
   GEMINI_API_KEY=...
   GROQ_API_KEY=...
   CEREBRAS_API_KEY=...
   WP_URL=https://example.com
   WP_USERNAME=admin
   WP_APP_PASSWORD=abcd1234
   WC_CONSUMER_KEY=ck_xxx
   WC_CONSUMER_SECRET=cs_xxx
   REQUEST_DELAY_SECONDS=2
   AI_REQUEST_DELAY_SECONDS=3
   ```

5. **Prepare input files** in `inputs/`. The text file should contain one image URL per line; the CSV should have a header like `image_url`.

   Example `inputs/image_urls.txt`:
   ```txt
   https://example.com/images/product-001.jpg
   ```

6. **Run the pipeline** using one of the supported methods:
   * Direct URLs:
     ```powershell
     python main.py "https://example.com/image1.jpg" "https://example.com/image2.jpg"
     ```
   * Text file:
     ```powershell
     python main.py --input-file inputs/image_urls.txt
     ```
   * CSV file:
     ```powershell
     python main.py --csv inputs/products.csv
     ```

7. **Monitor logs** in `logs/pipeline.log` for progress, successes, and errors. Logs contain:
   * timestamp
   * product title
   * image URL
   * category ID
   * success/failure outcome

## Notes and tips

* The pipeline deletes downloaded images after successful product creation to conserve disk space.
* Products are created with `status=draft` and `catalog_visibility=catalog` so they appear only in catalogue mode.
* To change the AI provider, edit `AI_PROVIDER` in `.env`; the system will automatically fall back to the next provider if the first fails.
* Adjust `REQUEST_DELAY_SECONDS` and `AI_REQUEST_DELAY_SECONDS` if you hit rate limits.
* Extend `data/category_map.json` for custom category IDs.

## Advanced usage

* Add your own AI provider by extending `pipeline/ai_vision.py` and updating `config.py`.
* Bulk imports can be scheduled via `cron` or Windows Task Scheduler, pointing to the command above.
* For large batches, consider running multiple processes concurrently and monitor disk usage.

## Troubleshooting

* **Missing environment variable**: the script will exit with a clear error. Check `.env` and restart.
* **AI errors**: check logs, adjust delays or swap providers.
* **Network/API issues**: make sure WordPress credentials and site URL are correct and reachable.

Happy cataloging!

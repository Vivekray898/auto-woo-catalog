# Auto WooCommerce Catalog 🛒

Auto WooCommerce Catalog is a Python-based pipeline that automatically turns image URLs into WooCommerce catalogue products. It uses AI vision to generate titles, categories and SEO-friendly descriptions, then uploads media and creates products via the WordPress/WooCommerce REST APIs.

The project is designed to be easy to set up and run on Windows, macOS and Linux. Whether you have a few URLs or thousands of images stored in Cloudflare R2, the pipeline handles the details for you.

---

## 🚀 Features

- Download images from URLs, CSVs or Cloudflare R2 buckets
- Run AI vision models (Gemini, Groq, Cerebras) to guess product information
- Map results to WooCommerce category IDs using a JSON lookup
- Upload media to WordPress and create draft catalogue products
- Extensible architecture with separate `pipeline`, `woocommerce` and `wordpress` modules
- Detailed logging for debugging and auditing

---

## 🛠️ Prerequisites

1. **Python 3.11+** (3.12 tested) – install from [python.org](https://www.python.org/) or via your OS package manager.
2. **Git** (optional) – for cloning or updating the repository.
3. **WooCommerce-enabled WordPress site** with:
   - REST API credentials (consumer key/secret)
   - Admin username and application password
4. **AI provider API key** for one or more of:
   - Gemini
   - Groq
   - Cerebras
5. (Optional) **Cloudflare R2** account/bucket for automatic image sourcing.

---

## 📁 Repository Layout

```
auto_woo_catalog/
├── config.py              # environment loading and defaults
├── logger.py              # simple file logger
├── utils.py               # shared utilities
├── main.py                # CLI entrypoint
├── requirements.txt       # Python dependencies
├── README.md              # this document
├── SETUP.md               # quick setup guide (existing)
├── .env.example           # environment template
├── data/
│   └── category_map.json  # WooCommerce category lookup
├── inputs/                # sample inputs
│   ├── image_urls.txt
│   └── products.csv
├── pipeline/              # business logic
│   ├── ai_vision.py
│   ├── category_mapper.py
│   ├── downloader.py
│   └── seo_generator.py
├── wordpress/             # media uploader
│   └── media_uploader.py
├── woocommerce/           # product creator
│   └── product_creator.py
└── logs/
    └── pipeline.log       # persistent run log
```

---

## 🔧 Installation

Below are instructions for each major operating system. All commands assume you are inside the `auto_woo_catalog` directory.

### 1. Clone the repo (optional)

```bash
git clone https://github.com/yourusername/auto-woo-catalog.git
cd auto-woo-catalog
```

### 2. Create and activate a virtual environment

| OS         | Command                                                                          |
|------------|----------------------------------------------------------------------------------|
| Windows    | `python -m venv .venv`<br>`.venv\Scripts\activate` (PowerShell) or `\venv\Scripts\activate.bat` (CMD) |
| macOS/Linux| `python3 -m venv .venv`<br>`source .venv/bin/activate`                         |

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Copy `.env.example` to `.env` and fill in your credentials:

```env
AI_PROVIDER=gemini          # or groq, cerebras
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
# optional R2 settings:
R2_ENDPOINT=
R2_ACCESS_KEY=
R2_SECRET_KEY=
R2_BUCKET=
R2_PUBLIC_URL=
```

> **Note**: environment variables override defaults in `config.py`. Do not commit `.env` to version control.

---

## 📥 Preparing Inputs

Place data in the `inputs/` directory (create it if missing):

- `image_urls.txt` – one URL per line
- `products.csv` – must contain a header (e.g. `image_url`) and one row per product

Examples are already provided in the repository.

---

## 🏃 Running the Pipeline

Run `main.py` with any of the following options:

```bash
# Process individual URLs
python main.py "https://example.com/img1.jpg" "https://example.com/img2.jpg"

# Use a text file of URLs
python main.py --input-file inputs/image_urls.txt

# Use a CSV file with an "image_url" column
python main.py --csv inputs/products.csv

# Read from Cloudflare R2 bucket (see .env config)
python main.py --r2

# Mix options (e.g. file + URLs)
python main.py --input-file inputs/image_urls.txt https://foo.com/bar.jpg
```

The script will:
1. Download each image locally
2. Call the configured AI provider to generate a title, category, and description
3. Map the category name to a WooCommerce category ID using `data/category_map.json`
4. Upload the image to WordPress media library
5. Create a WooCommerce product in draft/catalog mode

By default the process is sequential. You can run multiple instances in parallel if you need higher throughput.

---

## 🕵️ Logging & Monitoring

All activity is recorded in `logs/pipeline.log`. Each line contains:

```
2026-03-06 12:00:00 | Title | https://... | cat_id=24 | success
```

Check the file for error details, API responses, or to audit what was created. Adjust `REQUEST_DELAY_SECONDS` and `AI_REQUEST_DELAY_SECONDS` in `.env` if you encounter rate-limit errors.

---

## 🧩 Configuration & Customization

- **Category mapping** – update `data/category_map.json` with additional WooCommerce category IDs.
- **AI providers** – modify `pipeline/ai_vision.py` to add new vendors and adjust prompt templates.
- **R2 support** – ensure `.env` contains valid keys and call `python main.py --r2`.
- **Product fields** – extend `woocommerce/product_creator.py` to set more fields (price, attributes, etc.).

Feel free to fork the repo and contribute improvements!

---

## 🛠 Troubleshooting

| Issue                         | Solution                                                                 |
|------------------------------|--------------------------------------------------------------------------|
| Missing env variable         | Check `.env`, restart the script                                         |
| AI provider failure          | Swap `AI_PROVIDER` or increase `AI_REQUEST_DELAY_SECONDS`               |
| WordPress auth error         | Verify `WP_URL`, `WP_USERNAME`, `WP_APP_PASSWORD`                      |
| WooCommerce key denied       | Check consumer key/secret in WooCommerce settings, refresh credentials  |
| Image download errors        | Validate URLs or network access                                          |
| R2 not returning objects     | Ensure `R2_BUCKET` and credentials are correct, `--r2` flag used        |

Logs usually contain enough detail to diagnose the problem. For persistent issues, rerun with `python -m pdb main.py` to step through.

---

## 📦 Packaging & Distribution

- To share the project, push to your GitHub repository and ensure the `README.md` is visible at the repo root.
- Users on any OS can follow the steps above to get started.
- Add a license file if you plan to open source the project.

---

## 🌟 Contributors

- Original author: _your name here_
- Contributions welcome via pull requests!

---

Happy cataloging and may your WooCommerce store grow effortlessly! 🎉

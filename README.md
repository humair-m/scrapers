# 🕷️ Scrapers

A high-performance, modular collection of Python web scrapers built for large-scale, distributed crawling. Ideal for research, data mining, and AI training datasets.

---

## 📁 Repository Structure

Each scraper lives in its own directory, with a clean separation of logic, configuration, and execution:

- `rekhta_khaka/` – Scrapes *khaka* (biographical sketches) from Rekhta.org, with support for resuming and word-count filtering.  
- `wikihow_scraper/` – Extracts step-by-step guides from WikiHow by category.  
- `utils/` – Shared utilities like caching, deduplication, proxy handling, HTML cleaning, and logging.  
- `standalone_scripts/` – Lightweight, independent scrapers for news sites, app reviews, feeds, and more.

---

## ⚙️ Features

- ✅ Robust error handling with retries & exponential backoff  
- ✅ Content-based deduplication  
- ✅ Resume from last checkpoint  
- ✅ Proxy rotation & rate limiting  
- ✅ File-based caching to reduce redundant requests  
- ✅ Modular CLI with customizable parameters  

---

## 🚀 Getting Started



## 🔧 Configuration

Each module contains a `configs` for fine-tuning:

- Target URLs or API endpoints  
- Rate limits, retries, and timeouts  
- Output paths and checkpoint files  
- Filtering rules (e.g., word count, categories)

---

## 📜 Standalone Scripts

These minimal-dependency scripts can be used independently:

- `bbc-articles.py` – Scrapes articles from BBC  
- `nature-articles.py` – Extracts research content from Nature  
- `independent.py` – Gets latest posts from The Independent  
- `play_store_reviews.py` – Fetches app reviews from Google Play  
- `wiki-how.py` – Collects WikiHow guides  
- `wiki-bio.py`, `wiki-source.py`, `wiki-good-articles.py` – Scrape Wikipedia bios, sources, and curated content  
- `get-feed-data.py` – Parses RSS/Atom feeds using `feedparser`  

---

## 📥 Installation

```bash
git clone https://github.com/humair-m/scrapers.git
cd scrapers
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## 🤝 Contributing

Pull requests, feature additions, and bug fixes are welcome. Follow the coding style in existing modules and submit a PR!

---

## 🧠 Author

Developed by [Humair M](https://github.com/humair-m)

---

## 📄 License

MIT License – Free to use, modify, and distribute for personal or commercial use.

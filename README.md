# 🕷️ Python Web Scrapers Collection

A comprehensive collection of Python web scrapers for extracting data from various popular websites and platforms. Each scraper is designed to be lightweight, efficient, and easy to use for research, data mining, and content aggregation purposes.

## 📁 Repository Structure

```
scrapers/
├── audio-chat.py              # Audio chat content scraper
├── bbc-articles.py            # BBC news articles scraper
├── cat-wise-wiki.py           # Category-wise Wikipedia content scraper
├── get-feed-data.py           # RSS/Atom feed parser and scraper
├── independent.py             # The Independent news scraper
├── play_store_reviews.py      # Google Play Store app reviews scraper
├── rekhta-data.py             # Rekhta.org Urdu literature scraper
├── wiki-bio.py                # Wikipedia biographies scraper
├── wiki-good-articles.py      # Wikipedia featured/good articles scraper
├── wiki-how.py                # WikiHow guides and tutorials scraper
├── wiki-source.py             # Wikisource documents scraper
├── requirements.txt           # Python dependencies
└── README.md                  # This file
```

## 🎯 Available Scrapers

### 📰 News & Media Scrapers

#### `bbc-articles.py`
- **Purpose**: Scrapes news articles from BBC
- **Features**: Article content, headlines, metadata extraction
- **Output**: Clean text format with article structure

#### `independent.py`
- **Purpose**: Extracts articles from The Independent
- **Features**: Latest news, opinion pieces, article metadata
- **Output**: Structured data with timestamps and categories

#### `get-feed-data.py`
- **Purpose**: Universal RSS/Atom feed parser
- **Features**: Multi-format feed support, content extraction
- **Output**: Standardized feed item structure

### 📚 Wikipedia Family Scrapers

#### `wiki-bio.py`
- **Purpose**: Scrapes biographical articles from Wikipedia
- **Features**: Person profiles, life events, biographical data
- **Output**: Structured biographical information

#### `wiki-good-articles.py`
- **Purpose**: Extracts Wikipedia's featured and good articles
- **Features**: High-quality curated content, article ratings
- **Output**: Premium Wikipedia content with quality metrics

#### `wiki-source.py`
- **Purpose**: Scrapes documents from Wikisource
- **Features**: Historical documents, literature, primary sources
- **Output**: Full-text documents with metadata

#### `wiki-how.py`
- **Purpose**: Extracts step-by-step guides from WikiHow
- **Features**: Tutorial content, images, step-by-step instructions
- **Output**: Structured how-to guides with visual elements

#### `cat-wise-wiki.py`
- **Purpose**: Category-based Wikipedia content extraction
- **Features**: Bulk scraping by categories, hierarchical content
- **Output**: Organized content by Wikipedia categories

### 🌐 Platform-Specific Scrapers

#### `play_store_reviews.py`
- **Purpose**: Collects app reviews from Google Play Store
- **Features**: User ratings, review text, app metadata
- **Output**: Review datasets with sentiment indicators

#### `rekhta-data.py`
- **Purpose**: Scrapes Urdu literature from Rekhta.org
- **Features**: Poetry, prose, biographical sketches (khaka)
- **Output**: Urdu literary content with translations

#### `audio-chat.py`
- **Purpose**: Audio chat content scraper
- **Features**: Conversation transcripts, audio metadata
- **Output**: Structured conversation data

## 🚀 Quick Start

### Installation

```bash
git clone https://github.com/humair-m/scrapers.git
cd scrapers
pip install -r requirements.txt
```

### Basic Usage

```bash
# Scrape BBC articles
python bbc-articles.py

# Get WikiHow tutorials
python wiki-how.py

# Extract Wikipedia biographies
python wiki-bio.py

# Parse RSS feeds
python get-feed-data.py --url "https://example.com/feed.xml"

# Scrape Play Store reviews
python play_store_reviews.py --app-id "com.example.app"

# Get Rekhta literature data
python rekhta-data.py

# Scrape The Independent articles
python independent.py

# Category-wise Wikipedia scraping
python cat-wise-wiki.py --category "Science"

# Wikisource documents
python wiki-source.py

# Wikipedia featured articles
python wiki-good-articles.py

# Audio chat content
python audio-chat.py
```

## ⚙️ Common Features

All scrapers in this collection share these characteristics:

- **🛡️ Robust Error Handling**: Built-in retries and graceful failure handling
- **⏱️ Rate Limiting**: Respectful crawling with configurable delays
- **💾 Multiple Output Formats**: JSON, CSV, TXT support
- **🔄 Resume Capability**: Continue interrupted scraping sessions
- **📝 Comprehensive Logging**: Detailed activity logs for debugging
- **🎛️ Configurable Parameters**: Customizable scraping behavior

## 📊 Output Formats

### JSON Output
```json
{
  "title": "Article Title",
  "content": "Article content...",
  "url": "source_url",
  "timestamp": "2024-01-01T12:00:00Z",
  "metadata": {
    "author": "Author Name",
    "category": "News"
  }
}
```

### CSV Output
```csv
title,content,url,timestamp,author,category
"Article Title","Article content...","source_url","2024-01-01T12:00:00Z","Author Name","News"
```

## 🔧 Configuration

Most scrapers support command-line arguments for customization:

```bash
# Common parameters
--output-dir /path/to/output    # Specify output directory
--format json|csv|txt           # Choose output format
--limit 100                     # Limit number of items
--delay 2                       # Delay between requests (seconds)
--verbose                       # Enable verbose logging
--resume                        # Resume from last checkpoint
```

## 📚 Dependencies

```txt
requests>=2.28.0
beautifulsoup4>=4.11.0
lxml>=4.9.0
feedparser>=6.0.10
selenium>=4.8.0
pandas>=1.5.0
```

## ⚠️ Usage Guidelines

- **Respect robots.txt**: Always check and follow website crawling policies
- **Rate Limiting**: Use appropriate delays between requests
- **Terms of Service**: Comply with website terms and conditions
- **Data Usage**: Use scraped data responsibly and ethically
- **Copyright**: Respect intellectual property rights

## 🤝 Contributing

Contributions are welcome! To add a new scraper or improve existing ones:

1. Fork the repository
2. Create a feature branch
3. Follow the existing code style and structure
4. Add appropriate error handling and logging
5. Include usage examples in docstrings
6. Submit a pull request

### Scraper Template Structure
```python
#!/usr/bin/env python3
"""
Scraper for [Website Name]
Author: [Your Name]
"""

import requests
from bs4 import BeautifulSoup
import json
import time
import logging

def scrape_content():
    """Main scraping function"""
    pass

if __name__ == "__main__":
    scrape_content()
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙋‍♂️ Support & Issues

- **GitHub Issues**: [Report bugs or request features](https://github.com/humair-m/scrapers/issues)
- **Documentation**: Check individual script docstrings for detailed usage
- **Examples**: Each scraper includes usage examples in comments

## 👨‍💻 Author

**Humair M**
- GitHub: [@humair-m](https://github.com/humair-m)
- Repository: [humair-m/scrapers](https://github.com/humair-m/scrapers)

---

## 🚀 Recent Features

- Multiple Wikipedia scrapers for different content types
- News aggregation from major outlets
- Mobile app review collection
- Multilingual content support (Urdu literature)
- Feed parsing for various content formats
- Audio content processing capabilities

---

⭐ **Star this repository** if you find these scrapers useful for your projects!

*Built for researchers, data scientists, and developers who need reliable web scraping tools*

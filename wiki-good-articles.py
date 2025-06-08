import requests
import time
import os
import random
import re
from tqdm import tqdm
import logging
from bs4 import BeautifulSoup
from collections import deque

class WikipediaGoodArticlesScraperOptimized:
    """A class to scrape all Wikipedia Good Articles from the listings page - Optimized for speed on subsequent runs."""

    # Constants
    API_URL = "https://en.wikipedia.org/w/api.php"
    GOOD_ARTICLES_URL = "https://en.wikipedia.org/wiki/Wikipedia:Good_articles/all"
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        "Mozilla/5.0 (X11; Linux x86_64)",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0)"
    ]

    def __init__(self, output_dir, batch_size=50, max_articles=None):
        """Initialize the scraper with configuration parameters"""
        self.output_dir = output_dir
        self.batch_size = batch_size
        self.max_articles = max_articles  # Set to None to download all articles
        self.downloaded_titles = set()
        self.download_queue = deque()
        self.downloaded_file = "downloaded_good_articles.txt"

        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler("good_articles_scraper.log"),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

        # Create output directory
        os.makedirs(self.output_dir, exist_ok=True)

        # Load previously downloaded titles
        self._load_downloaded_titles()

    def _get_headers(self):
        """Return random user agent headers to avoid detection"""
        return {"User-Agent": random.choice(self.USER_AGENTS)}

    def _sanitize_filename(self, title):
        """Sanitize the filename by replacing invalid characters"""
        return re.sub(r'[^a-zA-Z0-9_-]', '_', title)

    def _load_downloaded_titles(self):
        """Load previously downloaded article titles from a file"""
        if os.path.exists(self.downloaded_file):
            with open(self.downloaded_file, "r", encoding="utf-8") as file:
                self.downloaded_titles = set(file.read().splitlines())
            self.logger.info(f"Loaded {len(self.downloaded_titles)} previously downloaded titles")

    def _save_downloaded_titles(self):
        """Save downloaded article titles to a file"""
        with open(self.downloaded_file, "w", encoding="utf-8") as file:
            file.write("\n".join(self.downloaded_titles))
        self.logger.info(f"Saved {len(self.downloaded_titles)} downloaded titles")

    def _is_already_downloaded(self, title):
        """Check if an article is already downloaded based on the loaded set"""
        return title in self.downloaded_titles

    def fetch_good_articles_list(self):
        """Fetch the list of all Good Articles from the Wikipedia page"""
        self.logger.info(f"Fetching list of Good Articles from {self.GOOD_ARTICLES_URL}")

        try:
            response = requests.get(
                self.GOOD_ARTICLES_URL,
                headers=self._get_headers(),
                timeout=30
            )
            response.raise_for_status()

            # Parse the HTML
            soup = BeautifulSoup(response.text, 'html.parser')

            article_links = set()

            # Find all article links - these are direct links in the Wikipedia page
            all_links = soup.find_all('a')
            for link in all_links:
                href = link.get('href', '')
                title = link.get('title', '')

                if not href or not title:
                    continue
                if any(ns in title for ns in ['Wikipedia:', 'Category:', 'Template:', 'Help:', 'Portal:', 'File:', 'Special:', 'Talk:']):
                    continue
                if not href.startswith('/wiki/') or ':' in href or href.startswith('/wiki/Wikipedia:'):
                    continue
                if 'redlink=1' in href or 'action=' in href:
                    continue
                article_links.add(title)

            # Alternative approach: Find all list items and extract links
            if not article_links:
                self.logger.info("Trying alternative approach to find articles")
                for li in soup.find_all('li'):
                    link = li.find('a')
                    if link and link.get('href', '').startswith('/wiki/') and link.get('title'):
                        title = link.get('title')
                        if not any(ns in title for ns in ['Wikipedia:', 'Category:', 'Template:', 'Help:', 'Portal:', 'File:', 'Special:', 'Talk:']):
                            article_links.add(title)

            unique_articles = list(article_links)
            self.logger.info(f"Found {len(unique_articles)} unique Good Articles")
            return unique_articles

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error fetching Good Articles list: {e}")
            return []

    def fetch_articles_via_api(self):
        """Alternative approach: Use the Wikipedia API to get the Good Articles list"""
        self.logger.info("Using Wikipedia API to fetch Good Articles")

        params = {
            "action": "query",
            "format": "json",
            "list": "categorymembers",
            "cmtitle": "Category:Good articles",
            "cmlimit": "500",
            "cmtype": "page",
        }

        all_articles = set()
        cmcontinue = None

        while True:
            if cmcontinue:
                params["cmcontinue"] = cmcontinue

            try:
                response = requests.get(
                    self.API_URL,
                    params=params,
                    headers=self._get_headers(),
                    timeout=20
                )
                response.raise_for_status()
                data = response.json()

                if "query" in data and "categorymembers" in data["query"]:
                    members = data["query"]["categorymembers"]
                    for member in members:
                        all_articles.add(member["title"])

                if "continue" in data and "cmcontinue" in data["continue"]:
                    cmcontinue = data["continue"]["cmcontinue"]
                    self.logger.info(f"Continuing API query, fetched {len(all_articles)} so far")
                    time.sleep(0.1)
                else:
                    break

            except requests.exceptions.RequestException as e:
                self.logger.error(f"API request failed: {e}")
                break

        self.logger.info(f"Found {len(all_articles)} Good Articles via API")
        return list(all_articles)

    def fetch_article(self, title, retries=3):
        """Fetch the article content from Wikipedia API with retries"""
        params = {
            "action": "query",
            "format": "json",
            "titles": title,
            "prop": "extracts",
            "explaintext": True
        }

        for attempt in range(retries):
            try:
                response = requests.get(
                    self.API_URL,
                    params=params,
                    headers=self._get_headers(),
                    timeout=15
                )
                response.raise_for_status()
                data = response.json()
                pages = data.get("query", {}).get("pages", {})

                for page in pages.values():
                    if "extract" in page:
                        return page.get("extract")
                    else:
                        self.logger.warning(f"No extract found for {title}")
                        return None

            except requests.exceptions.RequestException as e:
                self.logger.warning(f"Error fetching {title} (attempt {attempt + 1} of {retries}): {e}")
                time.sleep(2 * (attempt + 1))

        self.logger.error(f"Failed to fetch article: {title} after {retries} attempts")
        return None

    def save_article(self, title, content):
        """Saves the article content to a file"""
        if not content:
            return False

        os.makedirs(self.output_dir, exist_ok=True)
        filename = os.path.join(self.output_dir, f"{self._sanitize_filename(title)}.txt")
        try:
            with open(filename, "w", encoding="utf-8") as file:
                file.write(content)
            return True
        except IOError as e:
            self.logger.error(f"Error saving article {title}: {e}")
            return False

    def process_batch(self, articles, start_idx, pbar):
        """Process a batch of articles"""
        end_idx = min(start_idx + self.batch_size, len(articles))
        batch = articles[start_idx:end_idx]

        for title in batch:
            if self._is_already_downloaded(title):
                pbar.update(1)
                continue

            self.logger.info(f"Downloading article: {title}")
            content = self.fetch_article(title)

            if content:
                if self.save_article(title, content):
                    self.downloaded_titles.add(title)
            pbar.update(1)
            time.sleep(0.1)

        self._save_downloaded_titles()
        return end_idx

    def run(self):
        """Main method to fetch and save Wikipedia Good Articles"""
        articles = self.fetch_good_articles_list()

        if not articles:
            self.logger.info("Direct page parsing failed. Trying API approach...")
            articles = self.fetch_articles_via_api()

        if not articles:
            self.logger.error("No Good Articles found using any method. Exiting.")
            return

        if self.max_articles is not None:
            articles = articles[:self.max_articles]

        # Filter out already downloaded articles *before* processing
        articles_to_download = [title for title in articles if not self._is_already_downloaded(title)]
        total_to_download = len(articles_to_download)

        self.logger.info(f"Found {len(articles)} Good Articles in total.")
        self.logger.info(f"Already have {len(self.downloaded_titles)} articles downloaded.")
        self.logger.info(f"Starting to download {total_to_download} new Good Articles.")

        if total_to_download > 0:
            with tqdm(total=total_to_download, desc="Downloading Good Articles") as pbar:
                start_idx = 0
                while start_idx < total_to_download:
                    start_idx = self.process_batch(articles_to_download, start_idx, pbar)
        else:
            self.logger.info("No new articles to download.")

        self._save_downloaded_titles()
        self.logger.info(f"Finished processing Good Articles.")


if __name__ == "__main__":
    # Configuration
    OUTPUT_DIR = "/home/humair/wikipedia_good_articles"
    BATCH_SIZE = 50
    MAX_ARTICLES = None  # Set to None to download all articles

    # Create and run the scraper
    scraper = WikipediaGoodArticlesScraperOptimized(OUTPUT_DIR, BATCH_SIZE, MAX_ARTICLES)
    scraper.run()

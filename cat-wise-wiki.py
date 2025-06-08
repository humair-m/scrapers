import requests
import time
import os
import random
import re
from bs4 import BeautifulSoup
from tqdm import tqdm
import logging
import urllib.parse

class WikipediaGoodArticlesScraper:
    """A class to scrape good articles from Wikipedia's Engineering and Technology category"""
    
    # Constants
    GOOD_ARTICLES_URL = ""
    API_URL = "https://en.wikipedia.org/w/api.php"
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        "Mozilla/5.0 (X11; Linux x86_64)",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0)"
    ]
    
    def __init__(self, output_dir):
        """Initialize the scraper with configuration parameters"""
        self.output_dir = output_dir
        self.downloaded_titles = set()
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
            self.logger.info(f"Loaded {len(self.downloaded_titles)} previously downloaded good articles")
    
    def _save_downloaded_titles(self):
        """Save downloaded article titles to a file"""
        with open(self.downloaded_file, "w", encoding="utf-8") as file:
            file.write("\n".join(self.downloaded_titles))
        self.logger.info(f"Saved {len(self.downloaded_titles)} downloaded good articles")
    
    def fetch_good_article_list(self):
        """Fetch the list of good articles from the engineering and technology page"""
        try:
            self.logger.info(f"Fetching good articles list from {self.GOOD_ARTICLES_URL}")
            response = requests.get(
                self.GOOD_ARTICLES_URL,
                headers=self._get_headers(),
                timeout=15
            )
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # The articles are usually listed in <li> tags within specific sections
            article_titles = []
            
            # Find all list items that contain links
            list_items = soup.find_all('li')
            for li in list_items:
                # Skip if there's no link in this list item
                if not li.find('a'):
                    continue
                
                # Get the link text (article title)
                link = li.find('a')
                title = link.get_text().strip()
                
                # Filter out non-article links
                href = link.get('href', '')
                if href.startswith('/wiki/') and ':' not in href and not href.startswith('/wiki/Wikipedia:'):
                    article_titles.append(title)
            
            self.logger.info(f"Found {len(article_titles)} good articles")
            return article_titles
            
        except Exception as e:
            self.logger.error(f"Error fetching good articles list: {e}")
            return []
    
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
                time.sleep(2 * (attempt + 1))  # Exponential backoff
                
        self.logger.error(f"Failed to fetch article: {title} after {retries} attempts")
        return None
    
    def save_article(self, title, content):
        """Saves the article content to a file"""
        if not content:
            return False
            
        filename = os.path.join(self.output_dir, f"{self._sanitize_filename(title)}.txt")
        try:
            with open(filename, "w", encoding="utf-8") as file:
                file.write(content)
            return True
        except IOError as e:
            self.logger.error(f"Error saving article {title}: {e}")
            return False
    
    def run(self):
        """Main method to fetch and save good articles"""
        # Fetch the list of good articles
        article_titles = self.fetch_good_article_list()
        
        if not article_titles:
            self.logger.error("No articles found to download.")
            return
        
        # Download each article
        with tqdm(total=len(article_titles), desc="Downloading good articles") as pbar:
            for i, title in enumerate(article_titles):
                if title in self.downloaded_titles:
                    self.logger.info(f"Skipping already downloaded article: {title}")
                    pbar.update(1)
                    continue
                
                self.logger.info(f"Downloading article {i+1}/{len(article_titles)}: {title}")
                content = self.fetch_article(title)
                
                if content:
                    if self.save_article(title, content):
                        self.downloaded_titles.add(title)
                        
                        # Save progress periodically
                        if len(self.downloaded_titles) % 10 == 0:
                            self._save_downloaded_titles()
                
                pbar.update(1)
                
                # Be nice to Wikipedia servers
                time.sleep(1)
        
        # Save the final list of downloaded titles
        self._save_downloaded_titles()
        self.logger.info(f"Finished downloading {len(self.downloaded_titles)} good articles")


if __name__ == "__main__":
    # Configuration
    OUTPUT_DIR = "/home/humair/good_articles_engineering_tech"
    
    # Create and run the scraper
    scraper = WikipediaGoodArticlesScraper(OUTPUT_DIR)
    scraper.run()

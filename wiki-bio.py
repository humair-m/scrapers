import requests
import time
import os
import random
import re
from tqdm import tqdm
import logging
from collections import deque

class WikipediaScraper:
    """A class to scrape articles from Wikipedia categories and their subcategories"""
    
    # Constants
    API_URL = "https://en.wikipedia.org/w/api.php"
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        "Mozilla/5.0 (X11; Linux x86_64)",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0)"
    ]
    
    def __init__(self, start_category, output_dir, max_articles=3000):
        """Initialize the scraper with configuration parameters"""
        self.start_category = start_category
        self.output_dir = output_dir
        self.max_articles = max_articles
        self.downloaded_titles = set()
        self.processed_categories = set()
        self.category_queue = deque([start_category])
        self.downloaded_file = "downloaded_titles.txt"
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler("scraper.log"),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # Create output directory
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Load previously downloaded titles
        self._load_downloaded_titles()
        
        # Also scan output directory for existing files
        self._scan_existing_files()
    
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
    
    def _scan_existing_files(self):
        """Scan output directory for existing files and add their titles to downloaded_titles"""
        file_count = 0
        # Walk through all subdirectories in the output directory
        for root, dirs, files in os.walk(self.output_dir):
            for file in files:
                if file.endswith('.txt'):
                    # Extract title from filename
                    title_unsanitized = os.path.splitext(file)[0]
                    # We can't perfectly reverse the sanitization, but we can add the sanitized version
                    self.downloaded_titles.add(title_unsanitized)
                    file_count += 1
        
        if file_count > 0:
            self.logger.info(f"Found {file_count} existing files in output directory")
    
    def _save_downloaded_titles(self):
        """Save downloaded article titles to a file"""
        with open(self.downloaded_file, "w", encoding="utf-8") as file:
            file.write("\n".join(self.downloaded_titles))
        self.logger.info(f"Saved {len(self.downloaded_titles)} downloaded titles")
    
    def _is_already_downloaded(self, title):
        """Check if an article is already downloaded by checking both the title set and the file system"""
        # Check if title is in our set of downloaded titles
        if title in self.downloaded_titles:
            return True
            
        # Also check if the file exists on disk (as a backup check)
        for category in os.listdir(self.output_dir):
            category_dir = os.path.join(self.output_dir, category)
            if os.path.isdir(category_dir):
                filename = os.path.join(category_dir, f"{self._sanitize_filename(title)}.txt")
                if os.path.exists(filename):
                    # If found, add to our set for future reference
                    self.downloaded_titles.add(title)
                    return True
                    
        return False
    
    def fetch_category_members(self, category, cmcontinue=None):
        """Fetch category members (articles/subcategories) in batches"""
        params = {
            "action": "query",
            "format": "json",
            "list": "categorymembers",
            "cmtitle": category,
            "cmlimit": "500",  # Fetch 500 at a time
            "cmtype": "page|subcat",  # Get both pages and subcategories
            "cmcontinue": cmcontinue
        }
        
        try:
            response = requests.get(
                self.API_URL, 
                params=params, 
                headers=self._get_headers(),
                timeout=15
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error fetching category members: {e}")
            time.sleep(2)  # Backoff before caller retries
            return {"query": {"categorymembers": []}}
    
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
    
    def save_article(self, category, title, content):
        """Saves the article content to a subdirectory within the category folder"""
        if not content:
            return False
            
        category_dir = os.path.join(self.output_dir, self._sanitize_filename(category))
        os.makedirs(category_dir, exist_ok=True)
        
        filename = os.path.join(category_dir, f"{self._sanitize_filename(title)}.txt")
        try:
            with open(filename, "w", encoding="utf-8") as file:
                file.write(content)
            return True
        except IOError as e:
            self.logger.error(f"Error saving article {title}: {e}")
            return False
    
    def process_category(self, category, fetched_articles, pbar):
        """Process a single category, downloading articles and finding subcategories"""
        cmcontinue = None
        
        while fetched_articles < self.max_articles:
            data = self.fetch_category_members(category, cmcontinue)
            
            # Process the current batch of articles
            for member in data.get("query", {}).get("categorymembers", []):
                # Skip if we already reached max articles
                if fetched_articles >= self.max_articles:
                    return fetched_articles
                
                title = member.get("title", "")
                
                # Process articles (namespace 0)
                if member.get("ns") == 0:
                    # Enhanced check for already downloaded articles
                    if self._is_already_downloaded(title):
                        self.logger.info(f"Skipping already downloaded article: {title}")
                        continue
                        
                    self.logger.info(f"Downloading article: {title}")
                    content = self.fetch_article(title)
                    
                    if content:
                        # Use category name without "Category:" prefix
                        cat_name = category.replace("Category:", "")
                        if self.save_article(cat_name, title, content):
                            self.downloaded_titles.add(title)
                            fetched_articles += 1
                            pbar.update(1)
                            
                            # Save progress periodically
                            if fetched_articles % 25 == 0:
                                self._save_downloaded_titles()
                
                # Add subcategories to queue (namespace 14)
                elif member.get("ns") == 14 and title not in self.processed_categories:
                    self.logger.info(f"Found subcategory: {title}")
                    self.category_queue.append(title)
            
            # Check if there are more items in this category
            if "continue" in data and "cmcontinue" in data["continue"]:
                cmcontinue = data["continue"]["cmcontinue"]
            else:
                break
                
            # Be nice to Wikipedia servers
            time.sleep(1)
            
        return fetched_articles
    
    def run(self):
        """Main method to fetch and save Wikipedia articles"""
        fetched_articles = 0
        
        self.logger.info(f"Starting to fetch up to {self.max_articles} articles from {self.start_category} and subcategories")
        self.logger.info(f"Already have {len(self.downloaded_titles)} articles downloaded from previous runs")
        
        with tqdm(total=self.max_articles, desc="Downloading articles") as pbar:
            while self.category_queue and fetched_articles < self.max_articles:
                current_category = self.category_queue.popleft()
                
                if current_category in self.processed_categories:
                    continue
                    
                self.logger.info(f"Processing category: {current_category}")
                self.processed_categories.add(current_category)
                
                fetched_articles = self.process_category(current_category, fetched_articles, pbar)
        
        # Save the final list of downloaded titles
        self._save_downloaded_titles()
        self.logger.info(f"Finished downloading {fetched_articles} articles from {len(self.processed_categories)} categories")
        self.logger.info(f"Categories processed: {', '.join(list(self.processed_categories)[:10])}...")


if __name__ == "__main__":
    # Configuration
    START_CATEGORY = "Category:Biology"
    OUTPUT_DIR = "/home/humair/all_biology_articles"
    MAX_ARTICLES = 3000
    
    # Create and run the scraper
    scraper = WikipediaScraper(START_CATEGORY, OUTPUT_DIR, MAX_ARTICLES)
    scraper.run()

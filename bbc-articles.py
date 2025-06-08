"""
Improved BBC Urdu Mass Article Scraper 

###############################
BY  : Humair Munir 
###############################
This script uses multiple concurrent agents to download articles from BBC Urdu.
It implements enhanced URL extraction, batching, logging, and error handling.
"""

import requests
from bs4 import BeautifulSoup
import json
import os
import time
import argparse
import logging
import concurrent.futures
import random
import re
from datetime import datetime
from urllib.parse import urljoin, urlparse, parse_qs
from tqdm import tqdm
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bbc_urdu_scraper.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("BBCUrduScraper")

class BBCUrduScraper:
    """A scraper for BBC Urdu articles"""
    
    def __init__(self, user_agent=None, delay_range=(1, 3)):
        """
        Initialize the scraper with a user agent and delay settings
        
        Args:
            user_agent (str): User agent string for requests
            delay_range (tuple): Range for random delays between requests (min, max) in seconds
        """
        self.headers = {
            'User-Agent': user_agent or 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9,ur;q=0.8',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0'
        }
        self.delay_range = delay_range
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.article_pattern = re.compile(r'/urdu/[a-z\-]+-\d+')
        self.visited_urls = set()
        
    def wait_random_delay(self):
        """Wait a random amount of time between requests to avoid rate limiting"""
        delay = random.uniform(*self.delay_range)
        time.sleep(delay)
    
    def scrape_article(self, url):
        """Scrape a BBC Urdu article from the given URL"""
        try:
            if url in self.visited_urls:
                logger.debug(f"Skipping already visited URL: {url}")
                return None
                
            self.visited_urls.add(url)
            
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            # Use html5lib parser which is more forgiving with malformed HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract article title
            title = soup.find('h1', class_=lambda c: c and 'bbc-' in c.lower())
            if not title:
                title = soup.find('h1')
            title_text = title.get_text().strip() if title else "Title not found"
            
            # Extract article date
            date_element = soup.find('time')
            date_text = date_element.get('datetime') if date_element else None
            
            if not date_text:
                # Try to find date in other formats
                date_element = soup.find('div', class_=lambda c: c and ('date' in c.lower() or 'time' in c.lower()))
                if date_element:
                    date_text = date_element.get_text().strip()
                else:
                    date_text = "Date not found"
            
            # Extract article content paragraphs using multiple approaches
            content_elements = self.extract_content_elements(soup)
            
            # Extract text from each content element
            content = []
            for element in content_elements:
                text = element.get_text().strip()
                if text and not any(text.startswith(exclude) for exclude in [
                    'Share this with',
                    'These are external links',
                    'Published',
                    'Last updated'
                ]):
                    tag_name = element.name
                    content.append({
                        "type": "heading" if tag_name in ["h2", "h3"] else "paragraph",
                        "content": text
                    })
            
            # Extract main image
            main_image = self.extract_main_image(soup)
            
            # Extract tags/categories
            tags = self.extract_tags(soup)
            
            # Extract author if available
            author = self.extract_author(soup)
            
            # Build the article data
            article_data = {
                "title": title_text,
                "date": date_text,
                "url": url,
                "content": content,
                "main_image": main_image,
                "tags": tags,
                "author": author,
                "scraped_at": datetime.now().isoformat()
            }
            
            # Make sure we have meaningful content before returning
            if len(content) < 3:
                logger.warning(f"Article has too little content: {url}")
                return None
                
            return article_data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching article {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error parsing article {url}: {e}")
            return None
    
    def extract_content_elements(self, soup):
        """Extract content elements using multiple extraction strategies"""
        content_elements = []
        
        # Try specific BBC class selectors first
        content_elements = soup.find_all(['p', 'h2', 'h3'], class_=lambda c: c and 'bbc-' in c.lower())
        
        # Try general article body approach
        if not content_elements or len(content_elements) < 3:
            article_body = soup.find('article') or soup.find('div', {'data-component': 'text-block'})
            if article_body:
                content_elements = article_body.find_all(['p', 'h2', 'h3'])
        
        # Try looking for the main content div
        if not content_elements or len(content_elements) < 3:
            main_content = soup.find('div', class_=lambda c: c and 'story-body' in c.lower())
            if main_content:
                content_elements = main_content.find_all(['p', 'h2', 'h3'])
                
        # Try even more general approach
        if not content_elements or len(content_elements) < 3:
            for div in soup.find_all('div', class_=lambda c: c and any(term in c.lower() for term in ['content', 'article', 'story', 'body'])):
                paragraphs = div.find_all(['p', 'h2', 'h3'])
                if len(paragraphs) > len(content_elements):
                    content_elements = paragraphs
        
        return content_elements
    
    def extract_main_image(self, soup):
        """Extract the main image from the article"""
        # Try multiple ways to find the main image
        main_image = None
        
        # Try finding image in standard BBC format
        img_element = soup.find('img', class_=lambda c: c and 'bbc-' in c.lower())
        if img_element and img_element.get('src'):
            main_image = img_element.get('src')
        
        # Try metadata
        if not main_image:
            img_element = soup.find('meta', {'property': 'og:image'})
            if img_element:
                main_image = img_element.get('content')
        
        # Try image inside figure
        if not main_image:
            figure = soup.find('figure')
            if figure:
                img = figure.find('img')
                if img and img.get('src'):
                    main_image = img.get('src')
        
        return main_image
    
    def extract_tags(self, soup):
        """Extract article tags or categories"""
        tags = []
        
        # Try different selectors for tags
        for tag_selector in [
            'a.bbc-1msyfg1', 
            'a[href*="/topics/"]',
            'li.tags__list-item a'
        ]:
            tag_elements = soup.select(tag_selector)
            for tag_element in tag_elements:
                tag_text = tag_element.get_text().strip()
                if tag_text and tag_text not in tags:
                    tags.append(tag_text)
        
        return tags
    
    def extract_author(self, soup):
        """Extract article author if available"""
        # Try different author selectors
        for author_selector in [
            'div.byline__name',
            'p.byline',
            'span[data-component="byline"]'
        ]:
            author_element = soup.select_one(author_selector)
            if author_element:
                return author_element.get_text().strip()
                
        return None
    
    def save_to_json(self, article_data, output_file):
        """Save the article data to a JSON file"""
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(article_data, f, ensure_ascii=False, indent=2)
            logger.debug(f"Article data saved to {output_file}")
            return True
        except Exception as e:
            logger.error(f"Error saving to JSON {output_file}: {e}")
            return False

    def get_article_urls_from_page(self, page_url):
        """Get article URLs from any BBC Urdu page"""
        try:
            response = self.session.get(page_url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            article_links = set()
            base_url = "https://www.bbc.com"
            
            # Find all links and filter for article patterns
            for link in soup.find_all('a', href=True):
                href = link.get('href')
                
                # Skip empty hrefs
                if not href:
                    continue
                    
                # Make absolute URL if needed
                if href.startswith('/'):
                    href = urljoin(base_url, href)
                elif not href.startswith(('http://', 'https://')):
                    continue
                    
                # Match URL pattern for articles
                if '/urdu/' in href and self.article_pattern.search(href):
                    article_links.add(href)
            
            return list(article_links)
            
        except Exception as e:
            logger.error(f"Error getting article URLs from page {page_url}: {e}")
            return []

    def explore_bbc_urdu(self, max_pages=20):
        """Explore BBC Urdu site to find articles through different approaches"""
        base_url = "https://www.bbc.com/urdu"
        all_article_urls = set()
        
        # Start with the homepage
        homepage_urls = self.get_article_urls_from_page(base_url)
        all_article_urls.update(homepage_urls)
        logger.info(f"Found {len(homepage_urls)} article URLs from homepage")
        
        # Look for section and category links on the homepage
        section_urls = self.get_section_urls()
        
        # Add some key RSS feeds
        rss_urls = [
            "https://feeds.bbci.co.uk/urdu/rss.xml",
            "https://feeds.bbci.co.uk/urdu/pakistan/rss.xml",
            "https://feeds.bbci.co.uk/urdu/world/rss.xml"
        ]
        
        # Process RSS feeds to get more article URLs
        for rss_url in rss_urls:
            try:
                rss_articles = self.get_articles_from_rss(rss_url)
                all_article_urls.update(rss_articles)
                logger.info(f"Found {len(rss_articles)} article URLs from RSS feed: {rss_url}")
                self.wait_random_delay()
            except Exception as e:
                logger.error(f"Error processing RSS feed {rss_url}: {e}")
        
        # Process each section page and its pagination
        pages_processed = 0
        for section_url in section_urls:
            if pages_processed >= max_pages:
                break
                
            try:
                # Process the main section page
                section_articles = self.get_article_urls_from_page(section_url)
                all_article_urls.update(section_articles)
                logger.info(f"Found {len(section_articles)} article URLs from section: {section_url}")
                pages_processed += 1
                self.wait_random_delay()
                
                # Try pagination for each section (pages 2 to 10)
                for page_num in range(2, 11):
                    if pages_processed >= max_pages:
                        break
                        
                    if '?' in section_url:
                        paginated_url = f"{section_url}&page={page_num}"
                    else:
                        paginated_url = f"{section_url}?page={page_num}"
                        
                    page_articles = self.get_article_urls_from_page(paginated_url)
                    
                    # If we get very few articles, likely reached end of pagination
                    if len(page_articles) < 3:
                        break
                        
                    all_article_urls.update(page_articles)
                    logger.info(f"Found {len(page_articles)} article URLs from section page {page_num}: {paginated_url}")
                    pages_processed += 1
                    self.wait_random_delay()
                    
            except Exception as e:
                logger.error(f"Error processing section {section_url}: {e}")
        
        # Try to explore by dates
        date_articles = self.explore_by_dates()
        all_article_urls.update(date_articles)
        
        return list(all_article_urls)
    
    def get_articles_from_rss(self, rss_url):
        """Get article URLs from RSS feed"""
        try:
            response = self.session.get(rss_url, timeout=30)
            response.raise_for_status()
            
            # Parse the XML
            soup = BeautifulSoup(response.text, 'xml')
            if not soup.find('item'):  # If no items found, try lxml parser
                soup = BeautifulSoup(response.text, 'lxml')
                
            article_urls = set()
            
            # Find all item links
            for item in soup.find_all('item'):
                link = item.find('link')
                if link and link.string:
                    url = link.string.strip()
                    if url and self.article_pattern.search(url):
                        article_urls.add(url)
            
            return list(article_urls)
        except Exception as e:
            logger.error(f"Error getting article URLs from RSS feed {rss_url}: {e}")
            return []
    
    def get_section_urls(self):
        """Get URLs for different sections of BBC Urdu"""
        base_url = "https://www.bbc.com/urdu"
        section_links = set()
        
        try:
            response = self.session.get(base_url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for navigation links
            for nav in soup.find_all(['nav', 'div'], class_=lambda c: c and ('nav' in c.lower() or 'menu' in c.lower())):
                for link in nav.find_all('a', href=True):
                    href = link.get('href')
                    if href and '/urdu/' in href:
                        full_url = urljoin(base_url, href)
                        # Filter out article URLs and only keep section URLs
                        if not self.article_pattern.search(full_url):
                            section_links.add(full_url)
            
            # Add known section/topic URLs
            known_sections = [
                "https://www.bbc.com/urdu/topics/cjgn7n9zzq7t",  # Pakistan
                "https://www.bbc.com/urdu/topics/cl8l9mveql2t",  # World
                "https://www.bbc.com/urdu/topics/cw57v2pmll9t",  # Sports
                "https://www.bbc.com/urdu/topics/c340q0p2585t",  # Science
                "https://www.bbc.com/urdu/topics/ckdxnx900n5t",  # Entertainment
                "https://www.bbc.com/urdu/topics/c5qvpq71pmko",  # Most popular
                "https://www.bbc.com/urdu/topics/cnq68n6wgzdt",  # Society
                "https://www.bbc.com/urdu/topics/cly4q0k279vt",  # Business
                "https://www.bbc.com/urdu/media/video",         # Videos
                "https://www.bbc.com/urdu/multimedia/photo_galleries"  # Photos
            ]
            
            for section in known_sections:
                section_links.add(section)
                
            # Add author/columnist pages
            author_page_urls = [
                "https://www.bbc.com/urdu/columns",
                "https://www.bbc.com/urdu/pakistan/columns"
            ]
            
            for author_page in author_page_urls:
                try:
                    section_links.add(author_page)
                    response = self.session.get(author_page, timeout=30)
                    response.raise_for_status()
                    author_soup = BeautifulSoup(response.text, 'html.parser')
                    
                    for author_link in author_soup.find_all('a', href=True):
                        href = author_link.get('href')
                        if href and '/urdu/' in href and 'author' in href:
                            section_links.add(urljoin(base_url, href))
                except Exception as e:
                    logger.error(f"Error fetching author page {author_page}: {e}")
                    
            # Add regional coverage
            region_sections = [
                "https://www.bbc.com/urdu/topics/czev38vq1q3t",  # India
                "https://www.bbc.com/urdu/topics/c1e0mzr9gvnt",  # US & Canada
                "https://www.bbc.com/urdu/topics/c404v74nk56t",  # Middle East
            ]
            
            for region in region_sections:
                section_links.add(region)
            
            logger.info(f"Found {len(section_links)} section URLs")
            return list(section_links)
            
        except Exception as e:
            logger.error(f"Error getting section URLs: {e}")
            return known_sections  # Return known sections if we fail to fetch
    
    def explore_by_dates(self):
        """Explore articles by date-based archive pages"""
        article_urls = set()
        
        # Try to access date archives for the past 30 days
        current_date = datetime.now()
        base_url = "https://www.bbc.com/urdu/topics/cd6jzjgn8gxt"  # BBC Urdu latest news
        
        for day_offset in range(1, 31):
            try:
                # Format the date for the URL
                target_date = current_date.replace(day=current_date.day - day_offset)
                date_str = target_date.strftime("%Y/%m/%d")
                
                # Try to access the archive page for this date
                archive_url = f"{base_url}/{date_str}"
                
                logger.info(f"Exploring archive for date: {date_str}")
                date_articles = self.get_article_urls_from_page(archive_url)
                article_urls.update(date_articles)
                
                logger.info(f"Found {len(date_articles)} articles from date {date_str}")
                self.wait_random_delay()
                
            except Exception as e:
                logger.error(f"Error exploring date archive {date_str}: {e}")
                
        return list(article_urls)

class BBCUrduMassScraper:
    """A class to handle mass scraping of BBC Urdu articles"""
    
    def __init__(self, output_dir="articles", num_workers=5, batch_size=50, delay_range=(1, 3)):
        """
        Initialize the mass scraper
        
        Args:
            output_dir (str): Directory to save scraped articles
            num_workers (int): Number of concurrent workers
            batch_size (int): Number of articles to process in each batch
            delay_range (tuple): Range for random delays between requests (min, max) in seconds
        """
        self.output_dir = output_dir
        self.num_workers = num_workers
        self.batch_size = batch_size
        self.delay_range = delay_range
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:90.0) Gecko/20100101 Firefox/90.0',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36 Edg/96.0.1054.62',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.81 Safari/537.36 OPR/80.0.4170.63'
        ]
        
        # Create output directory if it doesn't exist
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        # Create a subdirectory for this run
        self.run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_dir = os.path.join(output_dir, f"run_{self.run_timestamp}")
        os.makedirs(self.run_dir)
        
        # Create a progress file
        self.progress_file = os.path.join(self.run_dir, "progress.json")
        self.initialize_progress_file()
        
        # Set up logging
        self.logger = logging.getLogger(f"BBCUrduMassScraper_{self.run_timestamp}")
        handler = logging.FileHandler(os.path.join(self.run_dir, "scraper.log"))
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
        
        # Save URLs list separately
        self.urls_file = os.path.join(self.run_dir, "all_urls.json")
        
        # Set up lock for progress updates
        self.progress_lock = concurrent.futures.threading.Lock()
    
    def initialize_progress_file(self):
        """Initialize the progress file with default values"""
        try:
            progress_data = {
                "started_at": datetime.now().isoformat(),
                "total_articles": 0,
                "completed_articles": 0,
                "failed_articles": 0,
                "completed_urls": [],
                "failed_urls": [],
                "status": "running",
                "last_updated": datetime.now().isoformat()
            }
            
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(progress_data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            self.logger.error(f"Error initializing progress file: {e}")
            # Create an empty file as fallback
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                f.write("{}")
    
    def update_progress(self, completed_url=None, failed_url=None):
        """Update the progress file with the latest stats"""
        with self.progress_lock:
            try:
                try:
                    with open(self.progress_file, 'r', encoding='utf-8') as f:
                        progress = json.load(f)
                except (json.JSONDecodeError, FileNotFoundError):
                    # Reset progress file if corrupted
                    self.initialize_progress_file()
                    with open(self.progress_file, 'r', encoding='utf-8') as f:
                        progress = json.load(f)
                
                if completed_url:
                    progress["completed_articles"] += 1
                    progress["completed_urls"].append(completed_url)
                
                if failed_url:
                    progress["failed_articles"] += 1
                    progress["failed_urls"].append(failed_url)
                
                progress["last_updated"] = datetime.now().isoformat()
                
                with open(self.progress_file, 'w', encoding='utf-8') as f:
                    json.dump(progress, f, ensure_ascii=False, indent=2)
                    
            except Exception as e:
                self.logger.error(f"Error updating progress: {e}")
    
    def finalize_progress(self, status="completed"):
        """Finalize the progress file with the final stats"""
        with self.progress_lock:
            try:
                try:
                    with open(self.progress_file, 'r', encoding='utf-8') as f:
                        progress = json.load(f)
                except (json.JSONDecodeError, FileNotFoundError):
                    # Reset progress file if corrupted
                    self.initialize_progress_file()
                    with open(self.progress_file, 'r', encoding='utf-8') as f:
                        progress = json.load(f)
                
                progress["ended_at"] = datetime.now().isoformat()
                progress["status"] = status
                progress["last_updated"] = datetime.now().isoformat()
                
                # Calculate statistics
                total_processed = progress["completed_articles"] + progress["failed_articles"]
                success_rate = 0
                if total_processed > 0:
                    success_rate = (progress["completed_articles"] / total_processed) * 100
                
                progress["statistics"] = {
                    "success_rate": f"{success_rate:.2f}%",
                    "total_processed": total_processed,
                    "runtime_seconds": (datetime.fromisoformat(progress["ended_at"]) - 
                                        datetime.fromisoformat(progress["started_at"])).total_seconds()
                }
                
                with open(self.progress_file, 'w', encoding='utf-8') as f:
                    json.dump(progress, f, ensure_ascii=False, indent=2)
                    
            except Exception as e:
                self.logger.error(f"Error finalizing progress: {e}")
    
    def get_article_urls(self, target_count=1000):
        """
        Get article URLs from BBC Urdu using multiple approaches
        
        Args:
            target_count (int): Target number of article URLs to collect
        
        Returns:
            list: List of article URLs
        """
        self.logger.info(f"Starting URL collection with target of {target_count} articles")
        
        # Create a single scraper instance for URL collection
        scraper = BBCUrduScraper(
            user_agent=random.choice(self.user_agents),
            delay_range=self.delay_range
        )
        
        # Try to load previously saved URLs if available
        if os.path.exists(self.urls_file):
            try:
                with open(self.urls_file, 'r', encoding='utf-8') as f:
                    urls = json.load(f)
                    if isinstance(urls, list) and len(urls) > 0:
                        self.logger.info(f"Loaded {len(urls)} URLs from previous run")
                        return urls[:target_count]
            except Exception as e:
                self.logger.error(f"Error loading previous URLs: {e}")
        
        # Explore BBC Urdu site to find articles
        article_urls = scraper.explore_bbc_urdu(max_pages=30)
        
        if not article_urls:
            self.logger.error("Failed to collect any article URLs")
            return []
            
        self.logger.info(f"Collected {len(article_urls)} unique article URLs")
        
        # Sort URLs by recency based on URL patterns
        # BBC Urdu URLs often contain dates or numeric IDs that correlate with publication date
        sorted_urls = sorted(article_urls, key=lambda url: url.split('-')[-1] if '-' in url else '0', reverse=True)
        
        # Save the full list of URLs
        try:
            with open(self.urls_file, 'w', encoding='utf-8') as f:
                json.dump(sorted_urls, f, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"Error saving URLs to file: {e}")
        
        # Update progress with total articles
        try:
            with self.progress_lock:
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    progress = json.load(f)
                
                progress["total_articles"] = min(len(sorted_urls), target_count)
                
                with open(self.progress_file, 'w', encoding='utf-8') as f:
                    json.dump(progress, f, ensure_ascii=False, indent=2)
                    
        except Exception as e:
            self.logger.error(f"Error updating progress with total articles: {e}")
        
        return sorted_urls[:target_count]
    
    def process_article(self, worker_id, url):
        """
        Process a single article URL
        
        Args:
            worker_id (int): ID of the worker processing this article
            url (str): URL of the article to process
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Create a new scraper instance for this worker
            scraper = BBCUrduScraper(
                user_agent=random.choice(self.user_agents),
                delay_range=self.delay_range
            )
            
            # Generate a safe filename from the URL
            url_hash = str(hash(url))[-8:]  # Use part of hash to avoid filename issues
            safe_filename = f"article_{url_hash}.json"
            output_path = os.path.join(self.run_dir, safe_filename)
            
            # Check if we've already processed this URL
            if os.path.exists(output_path):
                self.logger.info(f"Worker {worker_id}: Article already exists, skipping {url}")
                self.update_progress(completed_url=url)
                return True

            # Add random delay to avoid overwhelming the server
            time.sleep(random.uniform(*self.delay_range))
            
            # Scrape the article
            self.logger.info(f"Worker {worker_id}: Processing article {url}")
            article_data = scraper.scrape_article(url)
            
            if not article_data:
                self.logger.warning(f"Worker {worker_id}: Failed to scrape article {url}")
                self.update_progress(failed_url=url)
                return False
            
            # Save article data to JSON file
            scraper.save_to_json(article_data, output_path)
            
            # Update progress
            self.update_progress(completed_url=url)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Worker {worker_id}: Error processing article {url}: {e}")
            self.update_progress(failed_url=url)
            return False
    
def run_batch(self, urls_batch, batch_num):
    """
    Process a batch of URLs with multiple workers
    
    Args:
        urls_batch (list): List of URLs to process
        batch_num (int): Batch number for logging
        
    Returns:
        tuple: Count of (successful, failed) articles
    """
    self.logger.info(f"Starting batch {batch_num} with {len(urls_batch)} URLs")
    
    success_count = 0
    failure_count = 0
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=self.num_workers) as executor:
        # Submit all URLs in this batch
        future_to_url = {
            executor.submit(self.process_article, worker_id, url): url 
            for worker_id, url in enumerate(urls_batch)
        }
        
        # Process results as they complete
        for future in tqdm(concurrent.futures.as_completed(future_to_url), 
                          total=len(future_to_url),
                          desc=f"Batch {batch_num}"):
            url = future_to_url[future]
            try:
                success = future.result()
                if success:
                    success_count += 1
                else:
                    failure_count += 1
            except Exception as e:
                self.logger.error(f"Exception occurred while processing {url}: {e}")
                failure_count += 1
                
    self.logger.info(f"Completed batch {batch_num}. Success: {success_count}, Failed: {failure_count}")
    return success_count, failure_count

def run_scraper(self, target_count=1000, resume=False):
    """
    Run the mass scraper
    
    Args:
        target_count (int): Target number of articles to scrape
        resume (bool): Whether to resume from a previous run
        
    Returns:
        tuple: Total count of (successful, failed) articles
    """
    start_time = time.time()
    self.logger.info(f"Starting BBC Urdu mass scraper, targeting {target_count} articles")
    
    # Get article URLs
    article_urls = self.get_article_urls(target_count)
    
    if not article_urls:
        self.logger.error("No article URLs found, aborting")
        self.finalize_progress(status="failed")
        return 0, 0
    
    self.logger.info(f"Found {len(article_urls)} article URLs to process")
    
    # Process articles in batches
    total_success = 0
    total_failure = 0
    
    if resume:
        # Load progress to determine which URLs to skip
        try:
            with open(self.progress_file, 'r', encoding='utf-8') as f:
                progress = json.load(f)
                
            completed_urls = set(progress.get("completed_urls", []))
            failed_urls = set(progress.get("failed_urls", []))
            processed_urls = completed_urls.union(failed_urls)
            
            # Filter out already processed URLs
            article_urls = [url for url in article_urls if url not in processed_urls]
            
            self.logger.info(f"Resuming previous run. {len(processed_urls)} articles already processed, {len(article_urls)} remaining")
            
        except Exception as e:
            self.logger.error(f"Error loading progress for resume: {e}")
            self.logger.info("Continuing with full URL list")
    
    # Create batches
    batches = [article_urls[i:i + self.batch_size] for i in range(0, len(article_urls), self.batch_size)]
    
    try:
        for batch_num, urls_batch in enumerate(batches, 1):
            success, failure = self.run_batch(urls_batch, batch_num)
            total_success += success
            total_failure += failure
            
            # Log progress after each batch
            self.logger.info(f"Overall progress: {total_success + total_failure}/{len(article_urls)} articles processed")
            self.logger.info(f"Success rate: {(total_success / (total_success + total_failure) * 100):.2f}%")
            
            # Sleep between batches to avoid overwhelming the server
            if batch_num < len(batches):
                sleep_time = random.uniform(5, 10)
                self.logger.info(f"Sleeping for {sleep_time:.2f} seconds before next batch")
                time.sleep(sleep_time)
                
    except KeyboardInterrupt:
        self.logger.warning("Keyboard interrupt detected, stopping gracefully")
        self.finalize_progress(status="interrupted")
        return total_success, total_failure
    except Exception as e:
        self.logger.error(f"Error in scraper execution: {e}")
        self.finalize_progress(status="error")
        return total_success, total_failure
        
    # Calculate and log statistics
    end_time = time.time()
    runtime_seconds = end_time - start_time
    hours, remainder = divmod(runtime_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    self.logger.info(f"BBC Urdu mass scraper completed in {int(hours)}h {int(minutes)}m {int(seconds)}s")
    self.logger.info(f"Total articles processed: {total_success + total_failure}")
    self.logger.info(f"Successful: {total_success}, Failed: {total_failure}")
    
    if total_success + total_failure > 0:
        success_rate = (total_success / (total_success + total_failure)) * 100
        self.logger.info(f"Success rate: {success_rate:.2f}%")
    
    # Finalize progress
    self.finalize_progress(status="completed")
    
    return total_success, total_failure

def create_summary_report(self):
    """Create a summary report of the scraping run"""
    try:
        # Load progress data
        with open(self.progress_file, 'r', encoding='utf-8') as f:
            progress = json.load(f)
        
        # Count articles by category or tag
        category_counts = {}
        date_counts = {}
        
        # Scan all article files
        for filename in os.listdir(self.run_dir):
            if filename.endswith('.json') and filename.startswith('article_'):
                try:
                    file_path = os.path.join(self.run_dir, filename)
                    with open(file_path, 'r', encoding='utf-8') as f:
                        article = json.load(f)
                    
                    # Count by tags/categories
                    for tag in article.get('tags', []):
                        if tag not in category_counts:
                            category_counts[tag] = 0
                        category_counts[tag] += 1
                    
                    # Count by date (just year-month)
                    date_str = article.get('date', '')
                    if date_str:
                        try:
                            # Try to extract year-month from datetime string
                            if 'T' in date_str:
                                date_str = date_str.split('T')[0]
                            
                            if '-' in date_str:
                                year_month = date_str[:7]  # Extract YYYY-MM
                                if year_month not in date_counts:
                                    date_counts[year_month] = 0
                                date_counts[year_month] += 1
                        except Exception:
                            pass
                except Exception as e:
                    self.logger.error(f"Error processing article file {filename}: {e}")
        
        # Create summary report
        report = {
            "run_id": self.run_timestamp,
            "start_time": progress.get("started_at"),
            "end_time": progress.get("ended_at"),
            "status": progress.get("status"),
            "statistics": {
                "total_articles": progress.get("total_articles", 0),
                "completed_articles": progress.get("completed_articles", 0),
                "failed_articles": progress.get("failed_articles", 0),
                "success_rate": progress.get("statistics", {}).get("success_rate", "0%"),
                "runtime_seconds": progress.get("statistics", {}).get("runtime_seconds", 0)
            },
            "top_categories": sorted(category_counts.items(), key=lambda x: x[1], reverse=True)[:10],
            "articles_by_month": sorted(date_counts.items())
        }
        
        # Save report
        report_path = os.path.join(self.run_dir, "summary_report.json")
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
            
        self.logger.info(f"Summary report saved to {report_path}")
        
        # Also save as text file for easy reading
        text_report_path = os.path.join(self.run_dir, "summary_report.txt")
        with open(text_report_path, 'w', encoding='utf-8') as f:
            f.write(f"BBC Urdu Scraper Run Summary\n")
            f.write(f"==========================\n\n")
            f.write(f"Run ID: {self.run_timestamp}\n")
            f.write(f"Status: {progress.get('status')}\n")
            f.write(f"Start Time: {progress.get('started_at')}\n")
            f.write(f"End Time: {progress.get('ended_at')}\n\n")
            
            f.write(f"Statistics:\n")
            f.write(f"  Total Articles: {progress.get('total_articles', 0)}\n")
            f.write(f"  Completed: {progress.get('completed_articles', 0)}\n")
            f.write(f"  Failed: {progress.get('failed_articles', 0)}\n")
            f.write(f"  Success Rate: {progress.get('statistics', {}).get('success_rate', '0%')}\n")
            
            runtime = progress.get("statistics", {}).get("runtime_seconds", 0)
            hours, remainder = divmod(runtime, 3600)
            minutes, seconds = divmod(remainder, 60)
            f.write(f"  Runtime: {int(hours)}h {int(minutes)}m {int(seconds)}s\n\n")
            
            f.write(f"Top Categories:\n")
            for category, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
                f.write(f"  {category}: {count} articles\n")
            
            f.write(f"\nArticles by Month:\n")
            for date, count in sorted(date_counts.items()):
                f.write(f"  {date}: {count} articles\n")
                
        self.logger.info(f"Text summary report saved to {text_report_path}")
        
        return report_path
        
    except Exception as e:
        self.logger.error(f"Error creating summary report: {e}")
        return None

def main():
    """Main entry point for the script"""
    parser = argparse.ArgumentParser(description='BBC Urdu Mass Article Scraper')
    parser.add_argument('--count', type=int, default=100, help='Number of articles to scrape')
    parser.add_argument('--output', type=str, default='bbc_urdu_articles', help='Output directory')
    parser.add_argument('--workers', type=int, default=5, help='Number of concurrent workers')
    parser.add_argument('--batch-size', type=int, default=20, help='Batch size for processing')
    parser.add_argument('--resume', action='store_true', help='Resume from previous run')
    parser.add_argument('--min-delay', type=float, default=1.0, help='Minimum delay between requests')
    parser.add_argument('--max-delay', type=float, default=3.0, help='Maximum delay between requests')
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.count < 1:
        print("Error: Count must be at least 1")
        return 1
        
    if args.workers < 1:
        print("Error: Workers must be at least 1")
        return 1
        
    if args.batch_size < 1:
        print("Error: Batch size must be at least 1")
        return 1
        
    if args.min_delay < 0 or args.max_delay < 0 or args.min_delay > args.max_delay:
        print("Error: Invalid delay range")
        return 1
    
    # Create and run the scraper
    scraper = BBCUrduMassScraper(
        output_dir=args.output,
        num_workers=args.workers,
        batch_size=args.batch_size,
        delay_range=(args.min_delay, args.max_delay)
    )
    
    try:
        success, failure = scraper.run_scraper(
            target_count=args.count,
            resume=args.resume
        )
        
        # Create summary report
        report_path = scraper.create_summary_report()
        
        print(f"\nScraping completed.")
        print(f"Articles successfully scraped: {success}")
        print(f"Articles failed: {failure}")
        
        if report_path:
            print(f"Summary report saved to: {report_path}")
            
        return 0
        
    except KeyboardInterrupt:
        print("\nScraping interrupted by user.")
        return 130
    except Exception as e:
        print(f"\nAn error occurred: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())

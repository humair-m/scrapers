import requests
import time
import os
import random
import re
from bs4 import BeautifulSoup
from tqdm import tqdm
import logging
import urllib.parse

class WikisourceMysteryStoriesScraper:
    """A class to scrape mystery short stories from Wikisource"""
    
    # Constants
    MYSTERY_STORIES_URL = "https://en.wikisource.org/wiki/Category:Novels"
    BASE_URL = "https://en.wikisource.org"
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0"
    ]
    
    def __init__(self, output_dir="mystery_stories"):
        """Initialize the scraper with configuration parameters"""
        self.output_dir = output_dir
        self.downloaded_titles = set()
        self.downloaded_file = "downloaded_mystery_stories.txt"
        self.session = requests.Session()
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler("mystery_stories_scraper.log"),
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
        return {
            "User-Agent": random.choice(self.USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
    
    def _sanitize_filename(self, title):
        """Sanitize the filename by replacing invalid characters"""
        # Remove or replace invalid filename characters
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', title)
        sanitized = re.sub(r'[^\w\s\-_.]', '_', sanitized)
        sanitized = re.sub(r'\s+', ' ', sanitized).strip()
        # Limit filename length
        return sanitized[:200] if len(sanitized) > 200 else sanitized
    
    def _load_downloaded_titles(self):
        """Load previously downloaded story titles from a file"""
        if os.path.exists(self.downloaded_file):
            try:
                with open(self.downloaded_file, "r", encoding="utf-8") as file:
                    self.downloaded_titles = set(line.strip() for line in file if line.strip())
                self.logger.info(f"Loaded {len(self.downloaded_titles)} previously downloaded mystery stories")
            except Exception as e:
                self.logger.error(f"Error loading downloaded titles: {e}")
    
    def _save_downloaded_titles(self):
        """Save downloaded story titles to a file"""
        try:
            with open(self.downloaded_file, "w", encoding="utf-8") as file:
                file.write("\n".join(sorted(self.downloaded_titles)))
            self.logger.info(f"Saved {len(self.downloaded_titles)} downloaded mystery stories")
        except Exception as e:
            self.logger.error(f"Error saving downloaded titles: {e}")
    
    def fetch_mystery_stories_list(self, max_stories=None):
        """Fetch the list of mystery stories from the Wikisource category page"""
        stories = []
        next_page_url = self.MYSTERY_STORIES_URL
        page_count = 0
        max_pages = 50  # Safety limit
        
        while next_page_url and page_count < max_pages:
            try:
                self.logger.info(f"Fetching stories list from page {page_count + 1}")
                response = self.session.get(
                    next_page_url,
                    headers=self._get_headers(),
                    timeout=30
                )
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                page_stories = []
                
                # Look for the category page content more specifically
                category_content = soup.find('div', {'id': 'mw-pages'})
                if not category_content:
                    category_content = soup.find('div', class_='mw-category')
                if not category_content:
                    category_content = soup.find('div', class_='mw-category-group')
                
                if category_content:
                    # Find all links in the category listing
                    category_links = category_content.find_all('a', href=True)
                    
                    for link in category_links:
                        href = link.get('href', '')
                        title = link.get_text().strip()
                        
                        # Filter for actual story pages
                        if self._is_valid_story_link(href, title):
                            full_url = self.BASE_URL + href
                            page_stories.append({
                                'title': title,
                                'url': full_url
                            })
                
                # If no category content found, try fallback method
                if not page_stories:
                    self.logger.warning("Using fallback method to find story links")
                    # Look for links in the main content area
                    content_area = soup.find('div', {'id': 'mw-content-text'})
                    if content_area:
                        all_links = content_area.find_all('a', href=re.compile(r'^/wiki/[^:]+'))
                        
                        for link in all_links:
                            href = link.get('href', '')
                            title = link.get_text().strip()
                            
                            if self._is_valid_story_link(href, title):
                                full_url = self.BASE_URL + href
                                page_stories.append({
                                    'title': title,
                                    'url': full_url
                                })
                
                # Remove duplicates from this page
                seen_on_page = set()
                unique_page_stories = []
                for story in page_stories:
                    if story['title'] not in seen_on_page:
                        unique_page_stories.append(story)
                        seen_on_page.add(story['title'])
                
                stories.extend(unique_page_stories)
                self.logger.info(f"Found {len(unique_page_stories)} unique stories on page {page_count + 1}")
                
                # Check if we have enough stories
                if max_stories and len(stories) >= max_stories:
                    self.logger.info(f"Reached target of {max_stories} stories, stopping search")
                    break
                
                # Look for next page link
                next_page_url = self._find_next_page_url(soup)
                page_count += 1
                
                # Be respectful to the server
                time.sleep(random.uniform(0.1, 0.3))
                
            except Exception as e:
                self.logger.error(f"Error fetching stories list from page {page_count + 1}: {e}")
                break
        
        # Remove duplicates while preserving order
        unique_stories = []
        seen_titles = set()
        for story in stories:
            if story['title'] not in seen_titles:
                unique_stories.append(story)
                seen_titles.add(story['title'])
        
        self.logger.info(f"Found {len(unique_stories)} unique mystery stories")
        return unique_stories
    
    def _is_valid_story_link(self, href, title):
        """Check if a link is a valid story link"""
        if not href.startswith('/wiki/') or not title or len(title) <= 1:
            return False
        
        # Exclude non-story pages
        excluded_prefixes = [
            '/wiki/Category:', '/wiki/Template:', '/wiki/Help:',
            '/wiki/Wikisource:', '/wiki/User:', '/wiki/Talk:',
            '/wiki/File:', '/wiki/MediaWiki:', '/wiki/Special:'
        ]
        
        # Also exclude common navigation and metadata text
        excluded_titles = [
            'next 200', 'previous 200', 'view', 'edit', 'history',
            'what links here', 'related changes', 'upload file',
            'special pages', 'printable version', 'permanent link'
        ]
        
        title_lower = title.lower()
        if any(excluded in title_lower for excluded in excluded_titles):
            return False
        
        return not any(href.startswith(prefix) for prefix in excluded_prefixes)
    
    def _find_next_page_url(self, soup):
        """Find the URL for the next page of results"""
        # Look for various patterns of "next" links
        next_patterns = [
            re.compile(r'next.*200', re.IGNORECASE),
            re.compile(r'next.*page', re.IGNORECASE),
            re.compile(r'continue', re.IGNORECASE)
        ]
        
        for pattern in next_patterns:
            next_link = soup.find('a', string=pattern)
            if next_link and next_link.get('href'):
                return self.BASE_URL + next_link.get('href')
        
        # Also check for pagination links with "from=" parameter
        pagination_links = soup.find_all('a', href=re.compile(r'from='))
        for link in pagination_links:
            if 'next' in link.get_text().lower():
                return self.BASE_URL + link.get('href')
        
        return None
    
    def fetch_story_content(self, story_url, retries=3):
        """Fetch the story content from Wikisource with retries"""
        for attempt in range(retries):
            try:
                self.logger.debug(f"Fetching content from {story_url} (attempt {attempt + 1})")
                response = self.session.get(
                    story_url, 
                    headers=self._get_headers(), 
                    timeout=30
                )
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Check if this is a redirect or disambiguation page
                redirect_div = soup.find('div', class_='redirectMsg')
                if redirect_div:
                    self.logger.debug(f"Found redirect page: {story_url}")
                    # Try to follow the redirect
                    redirect_link = redirect_div.find('a')
                    if redirect_link and redirect_link.get('href'):
                        redirect_url = self.BASE_URL + redirect_link.get('href')
                        self.logger.debug(f"Following redirect to: {redirect_url}")
                        return self.fetch_story_content(redirect_url, retries=1)
                
                # Check for disambiguation pages
                if 'disambiguation' in soup.get_text().lower():
                    self.logger.debug(f"Skipping disambiguation page: {story_url}")
                    return None
                
                # Remove unwanted elements
                for element in soup.find_all(['div', 'span'], class_=re.compile(r'(mw-editsection|noprint|navigation|edit|metadata|navbox|mw-headline)')):
                    element.decompose()
                
                # Remove script and style elements
                for element in soup.find_all(['script', 'style', 'noscript']):
                    element.decompose()
                
                # Find the main content area - try multiple approaches
                content = None
                
                # Method 1: Look for the main parser output
                parser_output = soup.find('div', class_='mw-parser-output')
                if parser_output:
                    content = self._extract_wikisource_text(parser_output)
                
                # Method 2: Look for content text div
                if not content:
                    content_div = soup.find('div', {'id': 'mw-content-text'})
                    if content_div:
                        content = self._extract_wikisource_text(content_div)
                
                # Method 3: Look for specific Wikisource content patterns
                if not content:
                    # Look for poem or prose content
                    poem_divs = soup.find_all('div', class_=re.compile(r'poem|verse'))
                    if poem_divs:
                        content = '\n\n'.join([div.get_text().strip() for div in poem_divs if div.get_text().strip()])
                
                if content and len(content.strip()) > 200:  # Increased minimum length
                    return content
                
                # Debug information
                page_title = soup.find('h1', {'id': 'firstHeading'})
                title_text = page_title.get_text().strip() if page_title else "Unknown"
                
                # Check if this might be a collection/index page
                if any(word in title_text.lower() for word in ['collection', 'index', 'volume', 'contents', 'table of contents']):
                    self.logger.debug(f"Skipping collection/index page: {title_text}")
                    return None
                
                self.logger.debug(f"Page title: {title_text}")
                all_text = soup.get_text()
                self.logger.debug(f"Total page text length: {len(all_text)}")
                
                # Check if there's any substantial text at all
                if len(all_text.strip()) < 500:
                    self.logger.debug(f"Page has very little content: {story_url}")
                    return None
                
                self.logger.warning(f"No substantial story content found for {story_url}")
                return None
                        
            except requests.exceptions.RequestException as e:
                self.logger.warning(f"Error fetching {story_url} (attempt {attempt + 1}): {e}")
                if attempt < retries - 1:
                    time.sleep(0.2)  # Exponential backoff
                
        self.logger.error(f"Failed to fetch story from {story_url} after {retries} attempts")
        return None
    
    def _extract_wikisource_text(self, content_div):
        """Extract clean text content from Wikisource content div"""
        if not content_div:
            return None
        
        # Remove unwanted elements more specifically
        for element in content_div.find_all(['table', 'div'], class_=re.compile(r'(navbox|infobox|messagebox|ambox|toccolours|mbox)')):
            element.decompose()
        
        # Remove edit links and other UI elements
        for element in content_div.find_all(['span'], class_=re.compile(r'(mw-editsection|editsection)')):
            element.decompose()
        
        # Remove references and footnotes sections
        for element in content_div.find_all(['div', 'section'], id=re.compile(r'(references|footnotes|notes)')):
            element.decompose()
        
        # Try to find the actual story content
        # Look for paragraphs first
        paragraphs = content_div.find_all('p')
        if paragraphs:
            story_paras = []
            for p in paragraphs:
                text = p.get_text().strip()
                if text and len(text) > 30 and not self._is_navigation_text(text):
                    story_paras.append(text)
            
            if story_paras and len('\n\n'.join(story_paras)) > 200:
                return '\n\n'.join(story_paras)
        
        # If no good paragraphs, look for div content
        divs = content_div.find_all('div', recursive=False)
        for div in divs:
            # Skip navigation and metadata divs
            if div.get('class') and any('nav' in str(cls).lower() or 'meta' in str(cls).lower() 
                                      for cls in div.get('class')):
                continue
            
            text = div.get_text().strip()
            if text and len(text) > 200 and not self._is_navigation_text(text):
                return text
        
        # Fallback: get all text but filter better
        all_text = content_div.get_text().strip()
        if len(all_text) > 200:
            # Split into lines and filter out short/navigation lines
            lines = [line.strip() for line in all_text.split('\n') if line.strip()]
            content_lines = []
            
            for line in lines:
                if (len(line) > 20 and 
                    not self._is_navigation_text(line) and
                    not line.startswith('From ') and  # Common Wikisource header
                    not line.startswith('This work is')):  # License text
                    content_lines.append(line)
            
            if content_lines and len('\n'.join(content_lines)) > 200:
                return '\n\n'.join(content_lines)
        
        return None
    
    def _is_navigation_text(self, text):
        """Check if text appears to be navigation or metadata"""
        if not text or len(text) < 5:
            return True
            
        text_lower = text.lower()
        
        # Navigation indicators
        nav_indicators = [
            'edit', 'view source', 'history', 'what links here',
            'related changes', 'upload file', 'special pages',
            'printable version', 'permanent link', 'page information',
            'coordinates:', 'retrieved from', 'category:', 'hidden category',
            'this work is in the public domain', 'sister projects',
            'from wikisource', 'jump to navigation', 'jump to search',
            'contents', 'table of contents', 'next chapter', 'previous chapter'
        ]
        
        # Check for navigation patterns
        if any(indicator in text_lower for indicator in nav_indicators):
            return True
        
        # Check for very short lines that are likely headers/navigation
        if len(text) < 50 and any(word in text_lower for word in ['chapter', 'part', 'volume', 'book', 'section']):
            return True
        
        # Check for copyright/license text patterns
        copyright_patterns = [
            r'copyright.*\d{4}', r'public domain', r'creative commons',
            r'license', r'permission', r'rights reserved'
        ]
        
        if any(re.search(pattern, text_lower) for pattern in copyright_patterns):
            return True
        
        return False
    
    def save_story(self, title, content, author=None):
        """Save the story content to a file"""
        if not content:
            return False
        
        try:
            # Create filename
            filename_base = self._sanitize_filename(title)
            if author:
                author_clean = self._sanitize_filename(author)
                filename_base = f"{author_clean} - {filename_base}"
            
            filename = os.path.join(self.output_dir, f"{filename_base}.txt")
            
            # Handle potential filename conflicts
            counter = 1
            original_filename = filename
            while os.path.exists(filename):
                name, ext = os.path.splitext(original_filename)
                filename = f"{name}_{counter}{ext}"
                counter += 1
            
            with open(filename, "w", encoding="utf-8") as file:
                file.write(f"Title: {title}\n")
                if author:
                    file.write(f"Author: {author}\n")
                file.write("Source: Wikisource (https://en.wikisource.org)\n")
                file.write("Downloaded: " + time.strftime("%Y-%m-%d %H:%M:%S") + "\n")
                file.write("=" * 60 + "\n\n")
                file.write(content)
            
            self.logger.debug(f"Saved story to {filename}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving story '{title}': {e}")
            return False
    
    def extract_author_from_title(self, title):
        """Extract author name from title if it follows common patterns"""
        # Pattern 1: "Title (Author)"
        author_match = re.search(r'\(([^)]+)\)$', title)
        if author_match:
            potential_author = author_match.group(1).strip()
            # Check if it looks like an author name (not a year or other info)
            if not re.match(r'^\d{4}$', potential_author):
                return potential_author
        
        # Pattern 2: "Author/Title"
        if '/' in title and not title.startswith('The '):
            parts = title.split('/', 1)
            if len(parts) == 2:
                potential_author = parts[0].strip()
                # Simple check if it looks like a name
                if ' ' in potential_author or len(potential_author.split()) <= 3:
                    return potential_author
        
        return None
    
    def run(self, max_stories=None):
        """Main method to fetch and save mystery stories"""
        try:
            # Fetch the list of mystery stories
            self.logger.info("Starting to fetch mystery stories list...")
            stories = self.fetch_mystery_stories_list(max_stories=max_stories)
            
            if not stories:
                self.logger.error("No stories found to download.")
                return
            
            # Limit stories if specified (additional safety check)
            if max_stories and len(stories) > max_stories:
                stories = stories[:max_stories]
                self.logger.info(f"Limited to first {max_stories} stories")
            
            # Filter out already downloaded stories
            new_stories = [s for s in stories if s['title'] not in self.downloaded_titles]
            self.logger.info(f"Found {len(new_stories)} new stories to download (skipping {len(stories) - len(new_stories)} already downloaded)")
            
            if not new_stories:
                self.logger.info("All stories have already been downloaded!")
                return
            
            # Download each story
            successful_downloads = 0
            with tqdm(total=len(new_stories), desc="Downloading mystery stories") as pbar:
                for i, story in enumerate(new_stories):
                    title = story['title']
                    url = story['url']
                    
                    self.logger.info(f"Downloading story {i+1}/{len(new_stories)}: {title}")
                    content = self.fetch_story_content(url)
                    
                    if content:
                        author = self.extract_author_from_title(title)
                        if self.save_story(title, content, author):
                            self.downloaded_titles.add(title)
                            successful_downloads += 1
                            
                            # Save progress periodically
                            if successful_downloads % 10 == 0:
                                self._save_downloaded_titles()
                    else:
                        self.logger.warning(f"Failed to download content for: {title}")
                    
                    pbar.update(1)
                    
                    # Be respectful to Wikisource servers
                    time.sleep(random.uniform(0.2, 0.4))
            
            # Save the final list of downloaded titles
            self._save_downloaded_titles()
            self.logger.info(f"Finished! Successfully downloaded {successful_downloads} new mystery stories")
            self.logger.info(f"Total stories downloaded: {len(self.downloaded_titles)}")
            
        except KeyboardInterrupt:
            self.logger.info("Download interrupted by user. Saving progress...")
            self._save_downloaded_titles()
        except Exception as e:
            self.logger.error(f"Unexpected error during scraping: {e}")
            self._save_downloaded_titles()
        finally:
            self.session.close()


def main():
    """Main function to run the scraper"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Scrape mystery stories from Wikisource")
    parser.add_argument("--output-dir", default="mystery_stories", 
                       help="Output directory for downloaded stories")
    parser.add_argument("--max-stories", type=int, 
                       help="Maximum number of stories to download")
    parser.add_argument("--verbose", action="store_true", 
                       help="Enable verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create and run the scraper
    scraper = WikisourceMysteryStoriesScraper(args.output_dir)
    scraper.run(max_stories=args.max_stories)


if __name__ == "__main__":
    main()

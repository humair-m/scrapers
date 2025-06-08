#!/usr/bin/env python3
import os
import re
import time
import asyncio
import random
import argparse
import logging
import bs4
from typing import Set, List, Tuple, Dict, Optional
from datetime import datetime
from urllib.parse import urljoin, urlparse
from crawl4ai import AsyncWebCrawler

# Configuration with defaults (can be overridden by command line args)
DEFAULT_CONFIG = {
    "download_dir": "independenturdu_science",
    "track_file": "ind_tracked_articles.txt",
    "urls_file": "ind_article_urls.txt",
    "error_file": "ind_failed_articles.txt",
    "log_file": "ind_crawler.log",
    "max_downloads": 100000,
    "seed_url": "https://www.independenturdu.com/node/179878",
    "base_url": "https://www.independenturdu.com",
    "rate_limit": 0.5,  # Seconds between requests
    "retry_count": 3,   # Number of times to retry a failed download
    "retry_delay": 1,   # Seconds to wait between retries
    "batch_size": 10,   # URLs to process before recording progress
    "concurrent_requests": 3  # Maximum concurrent requests
}

# Match article URLs like /node/123456
URL_PATTERN = re.compile(r'https?://www\.independenturdu\.com/node/\d+')

# Setup logging
def setup_logging(log_file: str, debug: bool = False) -> None:
    """Configure logging settings"""
    level = logging.DEBUG if debug else logging.INFO
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

# Parse command line arguments
def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments to override default configuration"""
    parser = argparse.ArgumentParser(description='Crawl Independent Urdu science articles')
    
    parser.add_argument('--download-dir', type=str, default=DEFAULT_CONFIG["download_dir"],
                        help=f'Directory to save downloaded articles (default: {DEFAULT_CONFIG["download_dir"]})')
    parser.add_argument('--track-file', type=str, default=DEFAULT_CONFIG["track_file"],
                        help=f'File to track downloaded articles (default: {DEFAULT_CONFIG["track_file"]})')
    parser.add_argument('--urls-file', type=str, default=DEFAULT_CONFIG["urls_file"],
                        help=f'File to store article URLs (default: {DEFAULT_CONFIG["urls_file"]})')
    parser.add_argument('--error-file', type=str, default=DEFAULT_CONFIG["error_file"],
                        help=f'File to track failed downloads (default: {DEFAULT_CONFIG["error_file"]})')
    parser.add_argument('--log-file', type=str, default=DEFAULT_CONFIG["log_file"],
                        help=f'File to store logs (default: {DEFAULT_CONFIG["log_file"]})')
    parser.add_argument('--max-downloads', type=int, default=DEFAULT_CONFIG["max_downloads"],
                        help=f'Maximum number of articles to download (default: {DEFAULT_CONFIG["max_downloads"]})')
    parser.add_argument('--seed-url', type=str, default=DEFAULT_CONFIG["seed_url"],
                        help=f'URL to start crawling from (default: {DEFAULT_CONFIG["seed_url"]})')
    parser.add_argument('--rate-limit', type=float, default=DEFAULT_CONFIG["rate_limit"],
                        help=f'Seconds between requests (default: {DEFAULT_CONFIG["rate_limit"]})')
    parser.add_argument('--retry-count', type=int, default=DEFAULT_CONFIG["retry_count"],
                        help=f'Number of retries for failed downloads (default: {DEFAULT_CONFIG["retry_count"]})')
    parser.add_argument('--retry-delay', type=int, default=DEFAULT_CONFIG["retry_delay"],
                        help=f'Seconds to wait between retries (default: {DEFAULT_CONFIG["retry_delay"]})')
    parser.add_argument('--batch-size', type=int, default=DEFAULT_CONFIG["batch_size"],
                        help=f'Articles to process before saving progress (default: {DEFAULT_CONFIG["batch_size"]})')
    parser.add_argument('--concurrent-requests', type=int, default=DEFAULT_CONFIG["concurrent_requests"],
                        help=f'Maximum concurrent requests (default: {DEFAULT_CONFIG["concurrent_requests"]})')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--resume', action='store_true', help='Resume from previous crawl')
    parser.add_argument('--reset-errors', action='store_true', help='Retry previously failed URLs')
    
    return parser.parse_args()

async def setup_environment(config: Dict) -> None:
    """Create necessary directories and files if they don't exist"""
    os.makedirs(config["download_dir"], exist_ok=True)
    
    # Create files if they don't exist
    for filename in [config["track_file"], config["urls_file"], config["error_file"]]:
        if not os.path.exists(filename):
            open(filename, 'a').close()
    
    # Initialize URLs file with seed URL if empty and not resuming
    if os.path.getsize(config["urls_file"]) == 0:
        with open(config["urls_file"], 'w', encoding='utf-8') as uf:
            uf.write(config["seed_url"] + '\n')
            logging.info(f"Initialized URLs file with seed URL: {config['seed_url']}")

def load_tracked_urls(filename: str) -> Set[str]:
    """Load set of tracked URLs from file"""
    try:
        with open(filename, 'r', encoding='utf-8') as tf:
            return set(line.strip() for line in tf if line.strip())
    except Exception as e:
        logging.error(f"Error loading tracked URLs from {filename}: {e}")
        return set()

def update_urls_file(new_urls: Set[str], config: Dict) -> int:
    """Update URLs file with new URLs, avoiding duplicates"""
    try:
        existing = load_tracked_urls(config["urls_file"])
        
        urls_to_add = new_urls - existing
        if not urls_to_add:
            return 0
        
        with open(config["urls_file"], 'a', encoding='utf-8') as uf:
            for url in sorted(urls_to_add):
                uf.write(url + '\n')
        
        logging.debug(f"Added {len(urls_to_add)} new URLs to track")
        return len(urls_to_add)
    except Exception as e:
        logging.error(f"Error updating URLs file: {e}")
        return 0

def load_candidate_urls(filename: str) -> List[str]:
    """Load and deduplicate candidate URLs from file"""
    try:
        with open(filename, 'r', encoding='utf-8') as uf:
            # Remove duplicates while preserving order
            urls = []
            seen = set()
            for line in uf:
                url = line.strip()
                if url and url not in seen:
                    urls.append(url)
                    seen.add(url)
            return urls
    except Exception as e:
        logging.error(f"Error loading candidate URLs from {filename}: {e}")
        return []

def add_to_tracked(url: str, filename: str) -> None:
    """Add URL to tracked file"""
    try:
        with open(filename, 'a', encoding='utf-8') as tf:
            tf.write(url + '\n')
    except Exception as e:
        logging.error(f"Error adding {url} to {filename}: {e}")

def add_to_failed(url: str, reason: str, config: Dict) -> None:
    """Add URL to failed downloads file with reason and timestamp"""
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(config["error_file"], 'a', encoding='utf-8') as ef:
            ef.write(f"{url}\t{timestamp}\t{reason}\n")
    except Exception as e:
        logging.error(f"Error adding {url} to failed list: {e}")

async def extract_links(html: str, base_url: str) -> Set[str]:
    """Extract article links from HTML content"""
    links = set()
    try:
        soup = bs4.BeautifulSoup(html, 'html.parser')
        
        for a in soup.find_all('a', href=True):
            href = a['href']
            # Handle relative URLs
            full_url = href if href.startswith("http") else urljoin(base_url, href)
            
            # Match our article pattern
            if URL_PATTERN.match(full_url):
                # Remove trailing slashes and fragments
                clean_url = full_url.split('#')[0].rstrip('/')
                links.add(clean_url)
    except Exception as e:
        logging.error(f"Error extracting links: {e}")
    
    return links

def is_valid_article(html: str) -> bool:
    """Check if the downloaded content appears to be a valid article"""
    try:
        soup = bs4.BeautifulSoup(html, 'html.parser')
        
        # Check for article content indicators
        has_content = bool(soup.select('article') or 
                          soup.select('.article-body') or 
                          soup.select('.node__content'))
                          
        # Check for error page indicators
        is_error = bool(soup.select('.page-not-found') or 
                       'not found' in soup.text.lower() or
                       'error' in soup.title.text.lower() if soup.title else False)
        
        return has_content and not is_error
    except Exception as e:
        logging.error(f"Error validating article: {e}")
        return False

async def download_article(crawler: AsyncWebCrawler, url: str, config: Dict, 
                          tracked: Set[str], failed: Set[str]) -> Tuple[bool, Optional[str]]:
    """Download article with retry logic"""
    if url in tracked:
        logging.debug(f"Skipping already downloaded: {url}")
        return False, None
        
    article_id = url.rstrip('/').split('/')[-1]
    outfile = os.path.join(config["download_dir"], f"{article_id}.md")
    
    # Check if file already exists (extra safety check)
    if os.path.exists(outfile):
        logging.debug(f"File already exists for {url}, marking as tracked")
        add_to_tracked(url, config["track_file"])
        tracked.add(url)
        return False, None
    
    # Apply rate limiting with jitter to be nice to the server
    await asyncio.sleep(config["rate_limit"] * (0.8 + 0.4 * random.random()))
    
    # Try multiple times
    for attempt in range(1, config["retry_count"] + 1):
        try:
            result = await crawler.arun(url)
            
            # Validate content
            if not is_valid_article(result.html):
                if attempt < config["retry_count"]:
                    logging.warning(f"Invalid article content for {url}, retrying ({attempt}/{config['retry_count']})")
                    await asyncio.sleep(config["retry_delay"])
                    continue
                else:
                    reason = "Invalid article content"
                    logging.error(f"Failed to download valid article from {url}: {reason}")
                    add_to_failed(url, reason, config)
                    failed.add(url)
                    return False, None
            
            # Save content
            with open(outfile, 'w', encoding='utf-8') as out:
                # Add metadata header
                metadata = (
                    f"---\n"
                    f"source_url: {url}\n"
                    f"article_id: {article_id}\n"
                    f"downloaded_at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"---\n\n"
                )
                out.write(metadata + result.markdown)
            
            # Mark as tracked
            add_to_tracked(url, config["track_file"])
            tracked.add(url)
            
            return True, result.html
            
        except Exception as e:
            if attempt < config["retry_count"]:
                logging.warning(f"Error downloading {url} (attempt {attempt}/{config['retry_count']}): {e}")
                await asyncio.sleep(config["retry_delay"] * attempt)  # Exponential backoff
            else:
                logging.error(f"Failed to download {url} after {config['retry_count']} attempts: {e}")
                add_to_failed(url, str(e), config)
                failed.add(url)
                return False, None
    
    return False, None

async def process_batch(crawler: AsyncWebCrawler, urls: List[str], config: Dict, 
                       tracked: Set[str], failed: Set[str]) -> int:
    """Process a batch of URLs concurrently"""
    tasks = []
    for url in urls:
        if url in tracked or url in failed:
            continue
        
        task = download_article(crawler, url, config, tracked, failed)
        tasks.append(task)
        
        # If we've reached our concurrency limit, wait for some to complete
        if len(tasks) >= config["concurrent_requests"]:
            results = await asyncio.gather(*tasks)
            tasks = []
            
    # Wait for any remaining tasks
    if tasks:
        await asyncio.gather(*tasks)
    
    # Count successful downloads in this batch
    successful = sum(1 for url in urls if url in tracked and url not in failed)
    return successful

async def main() -> None:
    """Main crawler function"""
    # Parse arguments
    args = parse_arguments()
    
    # Create config from defaults and args
    config = {
        "download_dir": args.download_dir,
        "track_file": args.track_file,
        "urls_file": args.urls_file,
        "error_file": args.error_file,
        "log_file": args.log_file,
        "max_downloads": args.max_downloads,
        "seed_url": args.seed_url,
        "base_url": DEFAULT_CONFIG["base_url"],
        "rate_limit": args.rate_limit,
        "retry_count": args.retry_count,
        "retry_delay": args.retry_delay,
        "batch_size": args.batch_size,
        "concurrent_requests": args.concurrent_requests
    }
    
    # Setup logging
    setup_logging(config["log_file"], args.debug)
    logging.info(f"Starting Independent Urdu science crawler")
    
    # Setup environment
    await setup_environment(config)
    
    # Load tracking data
    tracked = load_tracked_urls(config["track_file"])
    failed = load_tracked_urls(config["error_file"]) if not args.reset_errors else set()
    candidates = load_candidate_urls(config["urls_file"])
    
    # Calculate remaining downloads
    count = len(tracked)
    remaining = config["max_downloads"] - count
    
    logging.info(f"Starting download: {count}/{config['max_downloads']} already done, {remaining} remaining")
    logging.info(f"Found {len(candidates)} candidate URLs, {len(failed)} previously failed")
    
    # Initialize crawler
    async with AsyncWebCrawler() as crawler:
        start_time = time.time()
        total_successful = 0
        batch_count = 0
        
        # Process URLs in batches
        for i in range(0, len(candidates), config["batch_size"]):
            if count >= config["max_downloads"]:
                logging.info(f"Reached maximum download limit of {config['max_downloads']}")
                break
                
            batch = candidates[i:i+config["batch_size"]]
            logging.info(f"Processing batch {batch_count+1} ({len(batch)} URLs)")
            
            # Process batch
            successful = await process_batch(crawler, batch, config, tracked, failed)
            total_successful += successful
            count = len(tracked)
            batch_count += 1
            
            # Extract new links from successful downloads
            new_links = set()
            for url in batch:
                if url in tracked and url not in failed:
                    try:
                        result = await crawler.arun(url, cache_only=True)
                        article_links = await extract_links(result.html, config["base_url"])
                        new_links.update(article_links)
                    except Exception as e:
                        logging.error(f"Error extracting links from {url}: {e}")
            
            # Update URLs file with new links
            if new_links:
                added = update_urls_file(new_links, config)
                if added > 0:
                    logging.info(f"Added {added} new URLs to queue")
                    
                    # Reload candidates if we're running low
                    if i + config["batch_size"] >= len(candidates):
                        new_candidates = load_candidate_urls(config["urls_file"])
                        # Only add URLs we haven't seen yet
                        candidates_set = set(candidates)
                        candidates.extend([url for url in new_candidates if url not in candidates_set])
                        logging.info(f"Updated candidate list, now have {len(candidates)} URLs")
            
            # Log progress
            elapsed = time.time() - start_time
            remaining = config["max_downloads"] - count
            rate = count / elapsed if elapsed > 0 else 0
            eta_seconds = remaining / rate if rate > 0 else 0
            
            logging.info(f"Progress: {count}/{config['max_downloads']} articles downloaded "
                        f"({total_successful} in this session)")
            logging.info(f"Rate: {rate:.2f} articles/sec, ETA: {eta_seconds/3600:.1f} hours")
            
            # Save after each batch by reloading tracked URLs for next batch
            tracked = load_tracked_urls(config["track_file"])
    
    # Final stats
    elapsed = time.time() - start_time
    rate = total_successful / elapsed if elapsed > 0 and total_successful > 0 else 0
    
    logging.info(f"Crawl completed")
    logging.info(f"Downloaded {total_successful} articles in {elapsed/60:.1f} minutes")
    logging.info(f"Average rate: {rate:.2f} articles/sec")
    logging.info(f"Total downloaded: {count}/{config['max_downloads']}")
    logging.info(f"Failed: {len(failed)}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Crawler stopped by user")
    except Exception as e:
        logging.critical(f"Unhandled exception: {e}", exc_info=True)

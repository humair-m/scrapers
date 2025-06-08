import os
import asyncio
import aiohttp
from datetime import datetime
from typing import Set, List
from pathlib import Path
from crawl4ai import AsyncWebCrawler
import logging
import re

# ===== Configuration =====
CONFIG = {
    "download_dir": "rekhta_ghazal_articles",
    "track_file": "tracked_ghazal_articles.txt",
    "urls_file": "/home/humair/rekhta_ghazals_links.txt",  # File containing all URLs to crawl
    "max_downloads": 100000,
    "url_pattern": re.compile(r"https?://(www\.)?rekhta\.org/ghazals/[a-z0-9-]+(?:-[a-z0-9-]+)*\?lang=ur"),
    "concurrent_limit": 3,
    "backup_interval": 20,
    "request_timeout": 30,
    "retry_attempts": 3,
}

# ===== Logging Setup =====
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("ghazal_crawler.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ===== File Management Functions =====
def setup_environment() -> None:
    """Set up directories and tracking files."""
    Path(CONFIG["download_dir"]).mkdir(exist_ok=True)
    Path(CONFIG["track_file"]).touch(exist_ok=True)
    logger.info(f"Environment setup complete. Download directory: {CONFIG['download_dir']}")

def backup_tracking_files() -> None:
    """Create timestamped backups of tracking files."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if not os.path.exists(CONFIG["track_file"]):
        return
    backup_name = f"{CONFIG['track_file']}.{timestamp}.bak"
    try:
        with open(CONFIG["track_file"], "r", encoding="utf-8") as src, open(backup_name, "w", encoding="utf-8") as dst:
            dst.write(src.read())
        logger.info(f"Created backup: {backup_name}")
    except Exception as e:
        logger.error(f"Failed to create backup of {CONFIG['track_file']}: {e}")

# ===== URL Management Functions =====
def load_tracked_urls() -> Set[str]:
    """Load URLs of already downloaded articles."""
    try:
        with open(CONFIG["track_file"], "r", encoding="utf-8") as tf:
            urls = {line.strip() for line in tf if line.strip()}
        logger.info(f"Loaded {len(urls)} tracked URLs")
        return urls
    except FileNotFoundError:
        logger.info(f"No tracked URLs file found, starting fresh")
        return set()
    except Exception as e:
        logger.error(f"Error loading tracked URLs: {e}")
        return set()

def load_candidate_urls() -> List[str]:
    """Load URLs to be processed from ghazal_urls.txt."""
    try:
        with open(CONFIG["urls_file"], "r", encoding="utf-8") as uf:
            urls = [line.strip() for line in uf if line.strip() and CONFIG["url_pattern"].match(line.strip())]
        logger.info(f"Loaded {len(urls)} valid candidate URLs from {CONFIG['urls_file']}")
        return urls
    except FileNotFoundError:
        logger.error(f"URLs file {CONFIG['urls_file']} not found")
        return []
    except Exception as e:
        logger.error(f"Error loading candidate URLs: {e}")
        return []

# ===== Download Functions =====
async def check_website_availability(url: str) -> bool:
    """Check if the website is reachable."""
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, timeout=CONFIG["request_timeout"]) as response:
                if response.status == 200:
                    logger.info(f"Website {url} is reachable")
                    return True
                logger.warning(f"Website {url} returned HTTP {response.status}")
                return False
        except Exception as e:
            logger.error(f"Website availability check failed for {url}: {e}")
            return False

async def download_article(crawler: AsyncWebCrawler, url: str, tracked: Set[str]) -> bool:
    """Download a single article with retries."""
    for attempt in range(CONFIG["retry_attempts"]):
        try:
            logger.info(f"Attempt {attempt + 1} to download {url}")
            result = await crawler.arun(url)
            if not result.markdown:
                logger.warning(f"No content retrieved for {url}")
                return False
            
            name = os.path.basename(url).split("?")[0]
            outfile = os.path.join(CONFIG["download_dir"], f"{name}.md")
            
            with open(outfile, "w", encoding="utf-8") as out:
                out.write(result.markdown)
            
            with open(CONFIG["track_file"], "a", encoding="utf-8") as tf:
                tf.write(url + "\n")
            
            tracked.add(url)
            logger.info(f"Successfully downloaded: {url}")
            return True
        except Exception as e:
            logger.error(f"Attempt {attempt + 1} failed for {url}: {e}")
            if attempt < CONFIG["retry_attempts"] - 1:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
            else:
                logger.error(f"Failed to download {url} after {CONFIG['retry_attempts']} attempts")
                return False

async def download_batch(crawler: AsyncWebCrawler, urls: List[str], tracked: Set[str]) -> int:
    """Download a batch of articles concurrently."""
    tasks = [download_article(crawler, url, tracked) for url in urls if url not in tracked]
    if not tasks:
        logger.info("No new URLs to download in this batch")
        return 0
    results = await asyncio.gather(*tasks, return_exceptions=True)
    await asyncio.sleep(1)  # Delay to avoid rate limiting
    return sum(1 for r in results if r is True)

# ===== Main Function =====
async def main():
    logger.info("Starting Rekhta Ghazal article crawler")
    
    # Check website availability
    if not await check_website_availability("https://www.rekhta.org"):
        logger.error("Website is unreachable. Exiting.")
        return
    
    # Setup
    setup_environment()
    backup_tracking_files()
    tracked = load_tracked_urls()
    
    # Load URLs directly from ghazal_urls.txt
    candidates = load_candidate_urls()
    candidates = [url for url in candidates if url not in tracked]
    
    if not candidates:
        logger.info("No URLs to process. Exiting.")
        return
    
    # Download articles
    async with AsyncWebCrawler() as crawler:
        downloaded_count = len(tracked)
        remaining = CONFIG["max_downloads"] - downloaded_count
        logger.info(f"Starting download: {downloaded_count}/{CONFIG['max_downloads']} already done, {remaining} remaining")
        logger.info(f"Candidate URLs to process: {len(candidates)}")
        
        successful_this_session = 0
        backup_counter = 0
        
        for i in range(0, len(candidates), CONFIG["concurrent_limit"]):
            if downloaded_count >= CONFIG["max_downloads"]:
                logger.info(f"Reached maximum download limit of {CONFIG['max_downloads']}")
                break
            
            batch = candidates[i:i + CONFIG["concurrent_limit"]]
            successful = await download_batch(crawler, batch, tracked)
            
            downloaded_count += successful
            successful_this_session += successful
            backup_counter += successful
            
            logger.info(f"Batch completed: {successful}/{len(batch)} articles downloaded successfully")
            logger.info(f"Progress: {downloaded_count}/{CONFIG['max_downloads']} total articles")
            
            if backup_counter >= CONFIG["backup_interval"]:
                backup_tracking_files()
                backup_counter = 0
    
    # Final backup
    backup_tracking_files()
    logger.info(f"Crawling session complete. Articles downloaded in this session: {successful_this_session}")
    logger.info(f"Total articles downloaded: {downloaded_count}")

if __name__ == "__main__":
    asyncio.run(main())

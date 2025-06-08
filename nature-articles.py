import os
import re
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from crawl4ai import AsyncWebCrawler

# === Configuration ===
SEED_URL = "https://www.nature.com/articles/s41586-025-09168-8"
BASE_DOMAIN = "www.nature.com"
ARTICLE_REGEX = re.compile(r"^/articles/[a-zA-Z0-9\-]+$")
DOWNLOAD_DIR = "nature_articles"
TRACK_FILE = "nature_tracked.txt"
MAX_DOWNLOADS = 100000
CONCURRENT_WORKERS = 40
MAX_DEPTH = 50

# === Setup ===
def setup_environment():
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    if not os.path.exists(TRACK_FILE):
        open(TRACK_FILE, 'a').close()

def load_tracked_urls():
    with open(TRACK_FILE, 'r', encoding='utf-8') as f:
        return set(line.strip() for line in f)

def save_tracked_url(url):
    with open(TRACK_FILE, 'a', encoding='utf-8') as f:
        f.write(url + '\n')

async def extract_article_links(session, url):
    """Extract article URLs from a given page."""
    try:
        async with session.get(url, timeout=30) as resp:
            if resp.status != 200:
                return set()
            html = await resp.text()
        soup = BeautifulSoup(html, "html.parser")

        found_links = set()
        for a in soup.find_all("a", href=True):
            href = a['href'].strip()
            parsed = urlparse(href)

            # Normalize relative URLs
            if not parsed.netloc:
                href = urljoin(url, href)
                parsed = urlparse(href)

            # Keep only links within BASE_DOMAIN
            if parsed.netloc != BASE_DOMAIN:
                continue

            # Only match article links
            if ARTICLE_REGEX.fullmatch(parsed.path):
                full_url = f"https://{parsed.netloc}{parsed.path}"
                found_links.add(full_url)

        return found_links

    except Exception as e:
        print(f"✗ Failed to extract from {url}: {e}")
        return set()

async def download_article(sem, crawler, url, tracked, total_downloaded):
    async with sem:
        try:
            result = await crawler.arun(url)
            slug = urlparse(url).path.strip("/").replace("/", "_")
            filename = slug + ".md"
            filepath = os.path.join(DOWNLOAD_DIR, filename)
            if result.markdown is not None:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(result.markdown)
            save_tracked_url(url)
            tracked.add(url)
            total_downloaded.append(1)
            print(f"✓ [{len(total_downloaded)}] Downloaded: {url}")
        except Exception as e:
            print(f"✗ Error downloading {url}: {e}")

async def crawl_articles(seed_url):
    setup_environment()
    tracked = load_tracked_urls()
    seen = set(tracked)
    queue = [(seed_url, 0)]
    total_downloaded = []
    print(f"Starting crawl. {len(tracked)} already done, {MAX_DOWNLOADS - len(tracked)} remaining.")

    sem = asyncio.Semaphore(CONCURRENT_WORKERS)
    async with aiohttp.ClientSession() as session:
        async with AsyncWebCrawler() as crawler:
            while queue and len(total_downloaded) < MAX_DOWNLOADS:
                batch, next_queue = [], []

                for url, depth in queue:
                    if url not in tracked:
                        batch.append((url, depth))
                if not batch:
                    break

                print(f"\n🔄 Processing {len(batch)} URLs at depth {batch[0][1]}...")

                tasks = [
                    download_article(sem, crawler, url, tracked, total_downloaded)
                    for url, _ in batch
                    if len(total_downloaded) < MAX_DOWNLOADS
                ]
                await asyncio.gather(*tasks)

                # Discover new links
                if batch[0][1] < MAX_DEPTH:
                    new_links = set()
                    for url, depth in batch:
                        discovered = await extract_article_links(session, url)
                        fresh_links = discovered - seen
                        new_links.update(fresh_links)
                        seen.update(fresh_links)
                        next_queue.extend((link, depth + 1) for link in fresh_links)

                    print(f"➕ Found {len(new_links)} new links.")

                queue = next_queue

    print(f"\n🎉 Done. Total downloaded: {len(total_downloaded)}")

# === Entry ===
if __name__ == "__main__":
    asyncio.run(crawl_articles(SEED_URL))

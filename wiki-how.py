import os
import re
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from crawl4ai import AsyncWebCrawler

# === Configuration ===
SEED_URL = "https://www.wikihow.com/Pronounce-Les-Miserables"
BASE_DOMAIN = "https://www.wikihow.com"
ARTICLE_PATTERN = re.compile(r"^https://www\.wikihow\.com/[\w\-]+$")
DOWNLOAD_DIR = "wikihow_articles"
TRACK_FILE = "wikihow_tracked.txt"
MAX_DOWNLOADS = 100000
BATCH_SIZE = 500

# === Setup ===
def setup_environment():
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    for file in [TRACK_FILE]:
        if not os.path.exists(file):
            open(file, 'a').close()

def load_tracked_urls():
    with open(TRACK_FILE, 'r', encoding='utf-8') as f:
        return set(line.strip() for line in f)

def save_tracked_url(url):
    with open(TRACK_FILE, 'a', encoding='utf-8') as f:
        f.write(url + '\n')

async def extract_article_links(session, url):
    try:
        async with session.get(url, timeout=30) as resp:
            if resp.status != 200:
                return set()
            html = await resp.text()
        soup = BeautifulSoup(html, "html.parser")
        links = set()
        for a in soup.find_all("a", href=True):
            href = urljoin(BASE_DOMAIN, a["href"])
            if ARTICLE_PATTERN.match(href):
                links.add(href)
        return links
    except Exception as e:
        print(f"✗ Failed to extract from {url}: {e}")
        return set()

async def crawl_articles(seed_url):
    setup_environment()
    tracked = load_tracked_urls()
    queue = [seed_url]
    seen = set(queue)
    total_downloaded = len(tracked)

    print(f"Starting crawl. {total_downloaded} already done, {MAX_DOWNLOADS - total_downloaded} remaining.")

    async with aiohttp.ClientSession() as session:
        async with AsyncWebCrawler() as crawler:
            while queue and total_downloaded < MAX_DOWNLOADS:
                batch = []
                while queue and len(batch) < BATCH_SIZE:
                    url = queue.pop(0)
                    if url not in tracked:
                        batch.append(url)

                print(f"\n🔄 Batch of {len(batch)} URLs...")

                for url in batch:
                    if total_downloaded >= MAX_DOWNLOADS:
                        break

                    try:
                        result = await crawler.arun(url)
                        filename = url.split("/")[-1] + ".md"
                        filepath = os.path.join(DOWNLOAD_DIR, filename)
                        with open(filepath, "w", encoding="utf-8") as f:
                            f.write(result.markdown)
                        tracked.add(url)
                        save_tracked_url(url)
                        total_downloaded += 1
                        print(f"✓ [{total_downloaded}] Downloaded: {url}")
                    except Exception as e:
                        print(f"✗ Error downloading {url}: {e}")

                # Expand queue with links from this batch
                print("🔍 Discovering new links from batch...")
                new_links = set()
                for url in batch:
                    discovered = await extract_article_links(session, url)
                    new_links.update(discovered - tracked - seen)
                queue.extend(sorted(new_links))
                seen.update(new_links)
                print(f"➕ Added {len(new_links)} new links to queue. Queue length: {len(queue)}")

    print(f"\n🎉 Done. Total downloaded: {total_downloaded}")

# === Entry ===
if __name__ == "__main__":
    asyncio.run(crawl_articles(SEED_URL))

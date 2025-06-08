import requests
import time
import hashlib
import json
import os
from tqdm import tqdm

FEED_URL = "https://text.pollinations.ai/feed"
SAVE_FILE = "pollinations_feed.jsonl"

def hash_line(line: str) -> str:
    """Return SHA256 hash of the line for deduplication."""
    return hashlib.sha256(line.encode("utf-8")).hexdigest()

def load_seen_hashes(filename):
    """Load hashes of already saved lines to avoid duplicates."""
    seen = set()
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            for line in f:
                h = hash_line(line.strip())
                seen.add(h)
    return seen

def stream_feed(url, save_file):
    """Stream data from the feed URL and save new entries to file."""
    seen_hashes = load_seen_hashes(save_file)
    print(f"Loaded {len(seen_hashes)} existing entries to skip duplicates.")
    
    pbar = tqdm(initial=len(seen_hashes), unit="entries", desc="Saved")
    
    try:
        with requests.get(url, stream=True, timeout=5) as r:
            r.raise_for_status()
            
            with open(save_file, "a", encoding="utf-8") as f:
                for line in r.iter_lines(decode_unicode=True):
                    if line:
                        if line.startswith("data: "):
                            json_str = line[len("data: "):].strip()
                            
                            # Skip empty data lines
                            if not json_str:
                                continue
                                
                            try:
                                # Validate JSON
                                json.loads(json_str)
                            except json.JSONDecodeError as e:
                                print(f"Invalid JSON skipped: {e}")
                                continue
                            
                            h = hash_line(json_str)
                            if h not in seen_hashes:
                                f.write(json_str + "\n")
                                f.flush()
                                seen_hashes.add(h)
                                pbar.update(1)
                                
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")
    finally:
        pbar.close()

def main():
    """Main function to continuously stream the feed with reconnection logic."""
    print(f"Starting Pollinations feed streamer...")
    print(f"Feed URL: {FEED_URL}")
    print(f"Save file: {SAVE_FILE}")
    print("Press Ctrl+C to stop\n")
    
    try:
        while True:
            stream_feed(FEED_URL, SAVE_FILE)
            print("Stream ended or connection dropped. Reconnecting in 5 seconds...")
            time.sleep(5)
    except KeyboardInterrupt:
        print("\nInterrupted by user. Exiting gracefully.")
    except Exception as e:
        print(f"Fatal error: {e}")

if __name__ == "__main__":
    main()

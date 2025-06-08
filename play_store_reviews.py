from google_play_scraper import reviews, Sort
import csv
import multiprocessing
import time
import random
from tqdm import tqdm

def scrape_google_play_reviews(app_id, country, max_reviews_per_country, result_queue):
    all_reviews = []
    count = 0
    pbar = tqdm(total=max_reviews_per_country, desc=f"Scraping reviews for {country}", unit='review')

    while count < max_reviews_per_country:
        try:
            new_reviews, _ = reviews(
                app_id,
                lang='en',
                country=country,
                sort=Sort.NEWEST,
                count=100,  # Fetch 100 reviews at a time
                continuation_token=None  # Fetch new reviews each time
            )
            if not new_reviews:
                break

            filtered_reviews = [review for review in new_reviews if review['score'] in [1, 2]]
            
            all_reviews.extend(filtered_reviews)
            count += len(filtered_reviews)
            pbar.update(len(filtered_reviews))
            time.sleep(random.uniform(0.5, 1))  # Reduced sleep interval

        except Exception as e:
            print(f"Error: {e}")
            time.sleep(10)  # Wait a bit before retrying
            continue

    pbar.close()
    result_queue.put(all_reviews)

def save_reviews_to_csv(reviews, filename):
    if reviews:
        keys = reviews[0].keys()
        with open(filename, 'a', newline='', encoding='utf-8') as output_file:
            dict_writer = csv.DictWriter(output_file, fieldnames=keys)
            if output_file.tell() == 0:
                dict_writer.writeheader()
            dict_writer.writerows(reviews)
    else:
        print("No reviews to save.")

def main():
    app_id = 'com.tencent.ig'  # Replace with the app ID for PUBG
    max_reviews = 100000  # Reduced total number of reviews
    max_reviews_per_country = 5000  # Reduced reviews per country
    country_codes = [
        'us', 'gb', 'ca', 'au', 'in', 'jp', 'de', 'fr', 'kr', 'br',
        'mx', 'ru', 'sa', 'ae', 'ng', 'ph', 'id', 'my', 'th', 'vn'
    ]
    
    result_queue = multiprocessing.Queue()
    processes = []

    for country in country_codes:
        process = multiprocessing.Process(target=scrape_google_play_reviews, args=(app_id, country, max_reviews_per_country, result_queue))
        processes.append(process)
        process.start()

    all_reviews = []
    for process in processes:
        process.join()
        all_reviews.extend(result_queue.get())

    save_reviews_to_csv(all_reviews, 'pubg_reviews_1_and_2.csv')

if __name__ == "__main__":
    main()

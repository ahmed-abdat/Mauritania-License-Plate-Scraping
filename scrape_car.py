import logging
from utils.config import load_config
from utils.scraper import scrape_main_page_images

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logging.getLogger('WDM').setLevel(logging.ERROR)

def main():
    config = load_config('config.ini')
    scrape_main_page_images(config)

if __name__ == "__main__":
    main()

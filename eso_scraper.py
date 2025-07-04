#!/usr/bin/env python3
"""
ESO Crown Store Free Items Scraper
Simple version for Ubuntu server - no Docker required
"""

import time
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import requests
from datetime import datetime
import json
import os

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('eso-scraper.log'),
        logging.StreamHandler()
    ]
)

def setup_driver():
    """Initialize Chrome driver"""
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1280,720')
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-images')
    
    driver = webdriver.Chrome(options=options)
    driver.implicitly_wait(10)
    return driver

def get_all_crownstore_urls(driver):
    """Extract all Crown Store URLs from the main page"""
    urls = set()
    
    try:
        logging.info("Discovering all Crown Store URLs...")
        driver.get("https://www.elderscrollsonline.com/en-us/crownstore")
        
        # Wait for page to load
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        time.sleep(5)
        
        # Find all links on the page
        links = driver.find_elements(By.TAG_NAME, "a")
        
        for link in links:
            try:
                href = link.get_attribute("href")
                if href and href.startswith("https://www.elderscrollsonline.com/en-us/crownstore"):
                    urls.add(href)
            except:
                continue
                
        # Always include the main page
        urls.add("https://www.elderscrollsonline.com/en-us/crownstore")
        
        logging.info(f"Found {len(urls)} Crown Store URLs to check")
        return list(urls)
        
    except Exception as e:
        logging.error(f"Error discovering URLs: {e}")
        # Fallback to main page
        return ["https://www.elderscrollsonline.com/en-us/crownstore"]

def extract_item_details(driver, item_container, category_url, item_url=None):
    """Extract detailed information about a free item"""
    item_details = {}
    
    try:
        # If item_url is provided, use it directly (new approach)
        if item_url:
            target_url = item_url
        else:
            # Original approach: extract URL from container
            target_url = None
            try:
                # Look for links specifically within this FREE item container
                link_elements = item_container.find_elements(By.XPATH, './/a[@href]')
                for link in link_elements:
                    href = link.get_attribute('href')
                    if href and '/crownstore/item/' in href:
                        target_url = href
                        break
            except:
                pass
            
            # If no individual item URL found, this might be a category header - skip it
            if not target_url:
                return None
        
        # Now get the item details from the actual item page and verify it's FREE
        item_name = None
        is_free = False
        is_eso_plus_free = False
        
        try:
            logging.info(f"Validating item: {target_url}")
            driver.get(target_url)
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(2)
            
            # Check for FREE indicators
            free_elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'FREE!')]")
            
            if not free_elements:
                logging.info(f"Item {target_url} is NOT free - skipping")
                return None
            
            # Proximity-based ESO Plus detection: check if the "FREE!" text itself is within eso-plus-loyalty
            # This avoids false positives from other ESO Plus items on the same page
            
            # Find all "FREE!" elements on the page
            all_free_elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'FREE!')]")
            
            logging.info(f"Found {len(all_free_elements)} FREE! elements on page")
            
            is_eso_plus_free_found = False
            
            for i, free_element in enumerate(all_free_elements):
                try:
                    logging.info(f"Analyzing FREE! element {i+1}:")
                    logging.info(f"  Element tag: {free_element.tag_name}")
                    logging.info(f"  Element text: '{free_element.text.strip()}'")
                    logging.info(f"  Element classes: {free_element.get_attribute('class')}")
                    
                    # Check parent element
                    try:
                        parent = free_element.find_element(By.XPATH, "./..")
                        logging.info(f"  Parent tag: {parent.tag_name}")
                        logging.info(f"  Parent classes: {parent.get_attribute('class')}")
                    except:
                        logging.info(f"  Could not get parent element")
                    
                    # Check if this specific "FREE!" element is within an eso-plus-loyalty container
                    # Check both the element itself AND its ancestors
                    loyalty_element = free_element.find_elements(By.XPATH, 
                        "./ancestor-or-self::*[contains(@class, 'eso-plus-loyalty')]")
                    
                    logging.info(f"  ESO Plus loyalty elements (self or ancestors) found: {len(loyalty_element)}")
                    
                    if loyalty_element:
                        # This "FREE!" text is within an eso-plus-loyalty container
                        is_eso_plus_free_found = True
                        logging.info(f"  ✓ This FREE! element IS within or has eso-plus-loyalty class")
                        break
                    else:
                        logging.info(f"  ✗ This FREE! element does NOT have eso-plus-loyalty class")
                        
                except Exception as e:
                    logging.warning(f"Error checking FREE! element {i+1} for ESO Plus ancestry: {e}")
                    continue
            
            # Additional check: look for "FREE!" text that contains "With ESO Plus Deal" in same element
            eso_plus_free_text = driver.find_elements(By.XPATH, 
                "//*[contains(text(), 'FREE!') and contains(text(), 'With ESO Plus Deal')]")
            
            logging.info(f"Found {len(eso_plus_free_text)} elements with both 'FREE!' and 'With ESO Plus Deal'")
            
            if eso_plus_free_text:
                is_eso_plus_free_found = True
                logging.info(f"Found FREE! text with 'With ESO Plus Deal' in same element")
            
            # Debug: show what we found
            logging.info(f"Proximity analysis - ESO Plus FREE found: {is_eso_plus_free_found}")
            
            # Determine final classification
            if is_eso_plus_free_found:
                is_free = True
                is_eso_plus_free = True
                logging.info(f"Item {target_url} is FREE with ESO Plus (FREE! element has eso-plus-loyalty class)")
            else:
                is_free = True
                is_eso_plus_free = False
                logging.info(f"Item {target_url} is FREE for everyone (FREE! element does not have eso-plus-loyalty class)")
            
            # Extract the actual item name from the item page
            name_selectors = [
                '//h1',
                '//h2', 
                '//h3',
                '//*[@class*="title"]',
                '//*[@class*="name"]',
                '//*[@class*="item-name"]',
                '//*[@class*="product-name"]'
            ]
            
            for selector in name_selectors:
                elements = driver.find_elements(By.XPATH, selector)
                for element in elements:
                    text = element.text.strip()
                    if text and len(text) > 2 and 'crown store' not in text.lower() and 'purchase crowns' not in text.lower():
                        item_name = text
                        break
                if item_name:
                    break
                    
        except Exception as e:
            logging.warning(f"Could not validate item {target_url}: {e}")
            return None
        
        if not item_name or not is_free:
            return None
            
        item_details = {
            'name': item_name,  # Keep name clean, no ESO Plus in the name
            'url': target_url,
            'category_url': category_url,
            'image_url': None,
            'is_eso_plus_free': is_eso_plus_free,
            'found_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Try to get the main item image while we're on the item page
        try:
            # Look for the main item image - be more selective
            main_image = None
            try:
                # Try to find the primary item image
                img_elements = driver.find_elements(By.XPATH, '//img[contains(@src, "/ape/uploads/")]')
                
                # Filter out duplicate images and find the largest/most relevant one
                unique_images = {}
                for img in img_elements:
                    src = img.get_attribute('src')
                    if (src and 
                        'akamaihd.net' in src and 
                        '/ape/uploads/' in src and
                        'icon-crown' not in src):
                        
                        # Get image dimensions to prefer larger images
                        try:
                            width = img.size.get('width', 0)
                            height = img.size.get('height', 0)
                            if width > 100 and height > 100:  # Only larger images
                                unique_images[src] = width * height
                        except:
                            unique_images[src] = 0
                
                # Get the largest unique image
                if unique_images:
                    main_image = max(unique_images.keys(), key=lambda k: unique_images[k])
                    item_details['image_url'] = main_image
                    logging.info(f"Found image: {main_image}")
                    
            except Exception as e:
                logging.warning(f"Could not get image for {item_name}: {e}")
                
        except Exception as e:
            logging.warning(f"Could not get image for {item_name}: {e}")
        
        return item_details
        
    except Exception as e:
        logging.warning(f"Error extracting item details: {e}")
        return None

def send_item_to_discord(item_details, webhook_url):
    """Send individual item to Discord immediately"""
    try:
        # Check if item is ESO Plus free and modify message accordingly
        if item_details.get('is_eso_plus_free', False):
            free_text = "FREE with ESO Plus!"
        else:
            free_text = "FREE!"
            
        message = f"**{item_details['name']} - {free_text}**\n{item_details['url']}"
        
        data = {
            "content": message,
            "avatar_url": "http://137.184.15.191/webhook-avatar.png"
        }
        
        response = requests.post(webhook_url, json=data)
        if response.status_code == 204:
            logging.info(f"Sent Discord message for: {item_details['name']} ({free_text})")
            return True
        else:
            logging.error(f"Failed to send Discord message for {item_details['name']}: {response.status_code}")
            return False
            
    except Exception as e:
        logging.error(f"Error sending item to Discord: {e}")
        return False

def load_posted_items():
    """Load previously posted items from file"""
    posted_file = 'posted_items.json'
    try:
        if os.path.exists(posted_file):
            with open(posted_file, 'r') as f:
                return set(json.load(f))
    except Exception as e:
        logging.warning(f"Could not load posted items: {e}")
    return set()

def save_posted_items(posted_items):
    """Save posted items to file"""
    posted_file = 'posted_items.json'
    try:
        with open(posted_file, 'w') as f:
            json.dump(list(posted_items), f, indent=2)
    except Exception as e:
        logging.error(f"Could not save posted items: {e}")

def scrape_free_items():
    """Scrape FREE items from all ESO Crown Store pages"""
    driver = setup_driver()
    free_items = []
    processed_urls = set()  # Track URLs we've already processed globally
    webhook_url = "https://discord.com/api/webhooks/1390384861101035600/gehtJILtdByfCLmW-pmLYc8haQlBsYLzPBxKqfsoQAfdoDPMK5c1fR6CpkVB7JVAnJ7S"
    
    # Load previously posted items to avoid duplicates
    posted_items = load_posted_items()
    new_posted_items = set(posted_items)  # Copy to track new additions
    logging.info(f"Loaded {len(posted_items)} previously posted items")
    
    try:
        # Get all Crown Store URLs
        all_urls = get_all_crownstore_urls(driver)
        
        # Prioritize URLs likely to have FREE items
        priority_urls = [
            "https://www.elderscrollsonline.com/en-us/crownstore/category/159",  # Companions
            "https://www.elderscrollsonline.com/en-us/crownstore/category/78",   # Quest Starters  
            "https://www.elderscrollsonline.com/en-us/crownstore/category/78#quest-starters",
            "https://www.elderscrollsonline.com/en-us/crownstore/category/78#currency",
            "https://www.elderscrollsonline.com/en-us/crownstore/category/71",   # Events/Prologue
            "https://www.elderscrollsonline.com/en-us/crownstore/category/1",    # DLC
            "https://www.elderscrollsonline.com/en-us/crownstore/eso-plus",      # ESO Plus deals
        ]
        
        # Remove priority URLs from all_urls and add them at the front
        remaining_urls = [url for url in all_urls if url not in priority_urls]
        urls_to_check = priority_urls + remaining_urls
        
        logging.info(f"Checking {len(priority_urls)} priority URLs first, then {len(remaining_urls)} remaining URLs")
        
        for url in urls_to_check:
            try:
                logging.info(f"Checking URL: {url}")
                driver.get(url)
                
                # Wait for page to load
                WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                time.sleep(3)  # Let JavaScript render
                
                # Find all FREE items
                free_elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'FREE!')]")
                logging.info(f"Found {len(free_elements)} potential FREE items on {url}")
                
                # First, collect all item URLs from this page to avoid stale element issues
                item_urls_to_check = set()  # Use set to avoid duplicates on same page
                for element in free_elements:
                    try:
                        # Find the item container
                        item_container = element.find_element(By.XPATH, "./ancestor::*[contains(@class, 'item') or contains(@class, 'product') or contains(@class, 'card')]")
                        
                        # Look for links specifically within this FREE item container
                        link_elements = item_container.find_elements(By.XPATH, './/a[@href]')
                        for link in link_elements:
                            href = link.get_attribute('href')
                            if href and '/crownstore/item/' in href:
                                item_urls_to_check.add(href)  # Set automatically deduplicates
                                break
                                
                    except Exception as e:
                        logging.warning(f"Error extracting URL from element on {url}: {e}")
                        continue
                
                # Now process each collected URL (skip if already processed globally)
                for item_url in item_urls_to_check:
                    if item_url in processed_urls:
                        logging.info(f"Skipping already processed item: {item_url}")
                        continue
                        
                    processed_urls.add(item_url)  # Mark as processed
                    
                    try:
                        # Extract detailed item information
                        item_details = extract_item_details(driver, None, url, item_url)
                        
                        if item_details:
                            # Create unique identifier for this item
                            item_id = f"{item_details['name']}-{item_details['is_eso_plus_free']}"
                            
                            if item_id not in posted_items:
                                # Add to our tracking lists
                                free_items.append(item_details)
                                new_posted_items.add(item_id)
                                
                                logging.info(f"Found FREE item: {item_details['name']} on {url}")
                                
                                # Send to Discord immediately
                                if webhook_url:
                                    send_item_to_discord(item_details, webhook_url)
                            else:
                                logging.info(f"Skipping already posted item: {item_details['name']}")
                            
                    except Exception as e:
                        logging.warning(f"Error processing item {item_url}: {e}")
                        continue
                        
            except Exception as e:
                logging.warning(f"Error checking URL {url}: {e}")
                continue
                
    except Exception as e:
        logging.error(f"Scraping failed: {e}")
    finally:
        driver.quit()
        
    # Save updated posted items list
    save_posted_items(new_posted_items)
    new_items_count = len(new_posted_items) - len(posted_items)
    logging.info(f"Found {new_items_count} new items, {len(new_posted_items)} total items tracked")
    
    return free_items

def main():
    # Get Discord webhook URL from environment variable
    webhook_url = "https://discord.com/api/webhooks/1390384861101035600/gehtJILtdByfCLmW-pmLYc8haQlBsYLzPBxKqfsoQAfdoDPMK5c1fR6CpkVB7JVAnJ7S"
    if not webhook_url:
        logging.error("DISCORD_WEBHOOK_URL environment variable not set")
        return
    
    # Scrape free items
    free_items = scrape_free_items()
    
    # Save results
    with open('eso-free-items.json', 'w') as f:
        json.dump(free_items, f, indent=2)
    
    logging.info("Scraper completed successfully")

if __name__ == "__main__":
    main()
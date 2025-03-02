import streamlit as st
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import re
import time
from fuzzywuzzy import fuzz
from datetime import datetime
import zipfile
import io
import os
import random

# Function to run the web scraping for exact matches
def scrape_facebook_marketplace_exact(city, product, min_price, max_price, city_code_fb):
    return scrape_facebook_marketplace(city, product, min_price, max_price, city_code_fb, exact=True)

# Function to run the web scraping for partial matches
def scrape_facebook_marketplace_partial(city, product, min_price, max_price, city_code_fb):
    return scrape_facebook_marketplace(city, product, min_price, max_price, city_code_fb, exact=False)

# Main scraping function with an exact match flag
def scrape_facebook_marketplace(city, product, min_price, max_price, city_code_fb, exact, sleep_time=3):
    chrome_options = Options()
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_argument('--start-maximized')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument(f'--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    # Add required preferences
    prefs = {
        "profile.default_content_setting_values.notifications": 2,
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False,
        "profile.managed_default_content_settings.images": 1
    }
    chrome_options.add_experimental_option("prefs", prefs)
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    try:
        service = Service('/usr/bin/chromedriver')
        browser = webdriver.Chrome(service=service, options=chrome_options)
        
        # Add anti-detection script
        browser.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': '''
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
            '''
        })
        
        st.info("Browser initialized successfully")
        
        exact_param = 'true' if exact else 'false'
        
        # Try different URL formats
        urls = [
            f"https://www.facebook.com/marketplace/{city_code_fb}/search/?query={product}&exact={exact_param}&minPrice={min_price}&maxPrice={max_price}",
            f"https://www.facebook.com/marketplace/search/?query={product}&exact={exact_param}&minPrice={min_price}&maxPrice={max_price}&region_id={city_code_fb}",
            f"https://m.facebook.com/marketplace/{city_code_fb}/search/?query={product}"
        ]
        
        for url in urls:
            st.info(f"Attempting to access URL: {url}")
            browser.get(url)
            time.sleep(15)
            
            if "login" not in browser.current_url.lower():
                st.info("Successfully accessed marketplace without login redirect")
                break
            else:
                st.warning(f"Login redirect detected for URL: {url}")
        
        st.info("Page loaded, checking for elements...")
        
        # Update the selectors to better target marketplace items
        selectors = [
            "div[class*='x3ct3a4'] a[role='link']",  # Main container with link
            "div[class*='x1xmf6yo']",  # Product card container
            "div[role='main'] div[style*='border-radius: 8px']"  # Product cards by style
        ]
        
        items = []
        for selector in selectors:
            items = browser.find_elements(By.CSS_SELECTOR, selector)
            if len(items) > 0:
                st.info(f"Found {len(items)} items using selector: {selector}")
                break
        
        # Scroll with random delays
        count = 0
        last_height = browser.execute_script("return document.body.scrollHeight")
        while count < 5:
            scroll_amount = random.randint(300, 800)
            browser.execute_script(f"window.scrollBy(0, {scroll_amount});")
            time.sleep(random.uniform(2.0, 4.0))
            new_height = browser.execute_script("return document.body.scrollHeight")
            count += 1
            st.info(f"Scroll iteration {count}/5")
            if new_height == last_height:
                break
            last_height = new_height
            
        # Try to find items again after scrolling
        for selector in selectors:
            items = browser.find_elements(By.CSS_SELECTOR, selector)
            if len(items) > 0:
                st.info(f"Found {len(items)} total items after scrolling using selector: {selector}")
                break
        
        # Extract data from items
        extracted_data = []
        for item in items:
            try:
                # Get all text content
                text_content = item.text
                st.write(f"Processing element with text: {text_content[:100]}")
                
                # Look for price and title
                if '$' in text_content:
                    lines = text_content.split('\n')
                    price_line = next((line for line in lines if '$' in line), None)
                    
                    if price_line:
                        price = ''.join(filter(str.isdigit, price_line))
                        price = int(price) if price else 0
                        
                        # Title is usually the longest line without $ or special characters
                        title_candidates = [line for line in lines if '$' not in line and len(line) > 5]
                        title = max(title_candidates, key=len) if title_candidates else "Unknown Title"
                        
                        link = item.get_attribute('href') or '#'
                        
                        if price > 0 and title:
                            extracted_data.append({
                                'title': title.strip(),
                                'price': price,
                                'price_text': price_line,
                                'location': city,
                                'url': link
                            })
                            st.info(f"Added item: {title.strip()} - ${price}")
            
            except Exception as e:
                st.warning(f"Failed to extract item data: {str(e)}")
                continue
        
        st.info(f"Successfully extracted {len(extracted_data)} items")
        
        # Create DataFrame
        items_df = pd.DataFrame(extracted_data)
        if not items_df.empty:
            items_df = items_df[['title', 'price', 'price_text', 'location', 'url']]
            
        return items_df, len(items)
        
    except Exception as e:
        st.error(f"Error during scraping: {str(e)}")
        return pd.DataFrame(), 0
    finally:
        try:
            browser.quit()
            st.info("Browser closed successfully")
        except:
            st.warning("Could not close browser properly")

# Streamlit UI
st.set_page_config(page_title="Facebook Marketplace Scraper", layout="wide")
st.title("🏷 Facebook Marketplace Scraper")
st.markdown("""Welcome to the Facebook Marketplace Scraper!  
Easily find products in your city and filter by price.""")

# Initialize session state for storing marketplaces and results
if "marketplaces" not in st.session_state:
    st.session_state["marketplaces"] = []

if "scraped_data" not in st.session_state:
    st.session_state["scraped_data"] = None

# Input fields with better layout and styling
with st.form(key='input_form'):
    col1, col2 = st.columns(2)
    
    with col1:
        city = st.text_input("City", placeholder="Enter city name...")
        product = st.text_input("Product", placeholder="What are you looking for?")
    
    with col2:
        min_price = st.number_input("Minimum Price", min_value=0, value=0, step=1)
        max_price = st.number_input("Maximum Price", min_value=0, value=1000, step=1)
    
    city_code_fb = st.text_input("City Code for Facebook Marketplace", placeholder="Enter city code...")

    col3, col4 = st.columns([3, 1])
    with col3:
        submit_button = st.form_submit_button(label="🔍 Scrape Data")
    with col4:
        add_button = st.form_submit_button(label="🟢 Add")

# Handle adding a new marketplace
if add_button:
    if city and product and min_price <= max_price and city_code_fb:
        st.session_state["marketplaces"].append({
            "city": city,
            "product": product,
            "min_price": min_price,
            "max_price": max_price,
            "city_code_fb": city_code_fb,
        })
        st.success("Marketplace added successfully!")
    else:
        st.error("Please fill all fields correctly.")

# Show the current list of marketplaces
if st.session_state["marketplaces"]:
    st.write("### Current Marketplaces:")
    for i, entry in enumerate(st.session_state["marketplaces"]):
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        col1.write(entry["city"])
        col2.write(entry["product"])
        col3.write(entry["min_price"])
        col4.write(entry["max_price"])
        col5.write(entry["city_code_fb"])
        if col6.button("❌ Remove", key=f"remove_{i}"):
            st.session_state["marketplaces"].pop(i)

# Handle scraping data
if submit_button:
    st.session_state["scraped_data"] = None
    individual_files = []

    if not st.session_state["marketplaces"]:
        st.error("Please add at least one marketplace to scrape data.")
    else:
        combined_df = pd.DataFrame()
        for marketplace in st.session_state["marketplaces"]:
            with st.spinner(f"Scraping data for {marketplace['city']}..."):
                items_df, total_links = scrape_facebook_marketplace_exact(
                    marketplace["city"],
                    marketplace["product"],
                    marketplace["min_price"],
                    marketplace["max_price"],
                    marketplace["city_code_fb"]
                )

            if not items_df.empty:
                if "scraped_data" not in st.session_state:
                    st.session_state["scraped_data"] = pd.DataFrame()

                st.session_state["scraped_data"] = pd.concat([st.session_state["scraped_data"], items_df], ignore_index=True)

                # Save individual result for each marketplace
                individual_file = io.StringIO()
                items_df.to_csv(individual_file, index=False)
                individual_file.seek(0)
                individual_files.append({
                    'name': f"{marketplace['city']}_{marketplace['product']}_result.csv",
                    'file': individual_file
                })

        if st.session_state["scraped_data"] is not None and not st.session_state["scraped_data"].empty:
            st.write("### Combined Match Results:")
            st.dataframe(st.session_state["scraped_data"])

            # Save combined CSV file
            combined_file = io.StringIO()
            st.session_state["scraped_data"].to_csv(combined_file, index=False)
            combined_file.seek(0)

            # Zip all individual and combined files into one package
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for file_data in individual_files:
                    zip_file.writestr(file_data['name'], file_data['file'].getvalue())
                zip_file.writestr("combined_results.csv", combined_file.getvalue())

            zip_buffer.seek(0)

            # Add download button
            st.download_button(
                label="Download All Results",
                data=zip_buffer,
                file_name="scraped_results.zip",
                mime="application/zip"
            )
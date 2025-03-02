import streamlit as st
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time
import io
import zipfile
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import json
import requests
from bs4 import BeautifulSoup
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import subprocess
import random

def get_chromium_version():
    try:
        result = subprocess.run(['chromium', '--version'], capture_output=True, text=True)
        version = result.stdout.split()[1]
        return version
    except:
        return "120.0.6099.224"

def scrape_facebook_marketplace(city, product, min_price, max_price, city_code_fb):
    try:
        st.write("Starting marketplace search...")
        
        # Enhanced Chrome options to avoid detection
        chrome_options = Options()
        chrome_options.add_argument('--headless=new')  # New headless mode
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')  # Hide automation
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--start-maximized')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        # Add required preferences
        prefs = {
            "profile.default_content_setting_values.notifications": 2,
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False,
            "profile.managed_default_content_settings.images": 1,
            "disk-cache-size": 4096
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        service = Service('/usr/bin/chromedriver')
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Modify the navigator properties to avoid detection
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': '''
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
            '''
        })
        
        # Use the mobile version of the site
        url = f"https://m.facebook.com/marketplace/{city_code_fb}/search/?query={product}&minPrice={min_price}&maxPrice={max_price}"
        st.write(f"Accessing URL: {url}")
        
        driver.get(url)
        st.write("Waiting for initial load...")
        time.sleep(15)  # Longer initial wait
        
        # Check if we're on a login page
        if "login" in driver.current_url.lower():
            st.write("Redirected to login page, trying alternative URL...")
            # Try the public search URL
            url = f"https://www.facebook.com/marketplace/search/?query={product}"
            driver.get(url)
            time.sleep(10)
        
        # Get page info
        st.write(f"Current URL: {driver.current_url}")
        st.write(f"Page title: {driver.title}")
        
        # Scroll with random delays
        for i in range(4):
            scroll_amount = random.randint(300, 800)  # Random scroll amount
            driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
            time.sleep(random.uniform(2.0, 4.0))  # Random delay
            st.write(f"Scroll {i+1} completed")
        
        # Try multiple selectors with more specific targeting
        selectors = [
            "//div[contains(@style, 'border-radius') and .//span[contains(text(), '$')]]",  # XPath for items with price
            "//a[contains(@href, '/marketplace/item/')]",  # XPath for marketplace items
            "//div[contains(@class, 'x1n2onr6')]//span[contains(text(), '$')]/..",  # XPath for price containers
            "div[role='main'] a[href*='/marketplace/item/']",  # CSS for item links
            "div[style*='width: 100%'][role='button']"  # CSS for item containers
        ]
        
        items = []
        for selector in selectors:
            st.write(f"\nTrying selector: {selector}")
            try:
                if '//' in selector:  # XPath selector
                    elements = driver.find_elements(By.XPATH, selector)
                else:  # CSS selector
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                
                st.write(f"Found {len(elements)} elements")
                
                if elements:
                    # Show sample of first element
                    sample_html = elements[0].get_attribute('outerHTML')
                    st.write("Sample element HTML:", sample_html[:200])
                    
                    for element in elements:
                        try:
                            # Get all text and HTML
                            text_content = element.text
                            html_content = element.get_attribute('outerHTML')
                            st.write(f"Processing element with text: {text_content[:100]}")
                            
                            # Look for price and title
                            if '$' in text_content:
                                # Split content into lines
                                lines = text_content.split('\n')
                                price_line = next((line for line in lines if '$' in line), None)
                                
                                if price_line:
                                    price = ''.join(filter(str.isdigit, price_line))
                                    price = int(price) if price else 0
                                    
                                    # Title is usually the longest line without $ or special characters
                                    title_candidates = [line for line in lines if '$' not in line and len(line) > 5]
                                    title = max(title_candidates, key=len) if title_candidates else "Unknown Title"
                                    
                                    link = element.get_attribute('href') or '#'
                                    
                                    if price > 0 and title:
                                        items.append({
                                            'title': title.strip(),
                                            'price': price,
                                            'link': link,
                                            'city': city,
                                            'search_term': product
                                        })
                                        st.write(f"Added item: {title.strip()} - ${price}")
                        
                        except Exception as e:
                            st.write(f"Error processing element: {str(e)}")
                            continue
                    
                    if items:
                        break
                        
            except Exception as e:
                st.write(f"Error with selector {selector}: {str(e)}")
                continue
        
        driver.quit()
        st.write("Browser closed")
        
        if items:
            df = pd.DataFrame(items)
            st.write("Scraped data preview:")
            st.write(df)
            return df, len(items)
        else:
            st.warning("No items found")
            return pd.DataFrame(), 0
            
    except Exception as e:
        st.error(f"Error during scraping: {str(e)}")
        if 'driver' in locals():
            driver.quit()
        return pd.DataFrame(), 0

# Streamlit UI
st.set_page_config(page_title="Facebook Marketplace Scraper", layout="wide")
st.title("🏷️ Facebook Marketplace Scraper")
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
    individual_files = []
    if not st.session_state["marketplaces"]:
        st.error("Please add at least one marketplace to scrape data.")
    else:
        for marketplace in st.session_state["marketplaces"]:
            with st.spinner(f"Scraping data for {marketplace['city']}..."):
                items_df, total_links = scrape_facebook_marketplace(
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

                    # Save individual result
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

            # Create download files
            combined_file = io.StringIO()
            st.session_state["scraped_data"].to_csv(combined_file, index=False)
            combined_file.seek(0)

            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for file_data in individual_files:
                    zip_file.writestr(file_data['name'], file_data['file'].getvalue())
                zip_file.writestr("combined_results.csv", combined_file.getvalue())

            zip_buffer.seek(0)

            st.download_button(
                label="Download All Results",
                data=zip_buffer,
                file_name="scraped_results.zip",
                mime="application/zip"
            )
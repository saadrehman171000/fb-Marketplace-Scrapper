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

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    return webdriver.Chrome(options=chrome_options)

def scrape_facebook_marketplace(city, product, min_price, max_price, city_code_fb):
    try:
        st.write("Starting scraper...")
        
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        # Simplified driver setup
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )
        
        url = f"https://www.facebook.com/marketplace/search?query={product}&exact=false"
        st.write(f"Accessing URL: {url}")
        
        driver.get(url)
        st.write("Waiting for page to load...")
        time.sleep(10)
        
        items = []
        
        # Scroll a few times to load more content
        for i in range(3):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            st.write(f"Scroll {i+1} completed")
        
        # Look for marketplace items using multiple selectors
        selectors = [
            "div[style*='border-radius: max']",  # Common marketplace item container
            "a[href*='/marketplace/item/']",     # Item links
            "div[style*='width: 100%'][role='button']"  # Item containers
        ]
        
        for selector in selectors:
            st.write(f"Trying selector: {selector}")
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            if elements:
                st.write(f"Found {len(elements)} items with selector {selector}")
                
                for element in elements:
                    try:
                        # Get the entire HTML of the element for debugging
                        html = element.get_attribute('outerHTML')
                        st.write(f"Processing element: {html[:200]}...")  # First 200 chars
                        
                        # Try to extract title
                        try:
                            title = element.find_element(By.CSS_SELECTOR, "span[style*='line-clamp']").text
                        except:
                            title = element.find_element(By.CSS_SELECTOR, "span").text
                        
                        # Try to extract price
                        try:
                            price_elem = element.find_element(By.CSS_SELECTOR, "span[style*='color: rgb(5, 5, 5)']")
                            price = price_elem.text
                        except:
                            price = "0"
                        
                        # Clean price
                        price_clean = ''.join(filter(str.isdigit, price))
                        price_clean = int(price_clean) if price_clean else 0
                        
                        # Get link
                        try:
                            link = element.get_attribute("href")
                            if not link:
                                link = element.find_element(By.CSS_SELECTOR, "a").get_attribute("href")
                        except:
                            link = "#"
                        
                        if title and price_clean > 0:
                            items.append({
                                'title': title,
                                'price': price_clean,
                                'link': link,
                                'city': city,
                                'search_term': product
                            })
                            st.write(f"Added item: {title} - ${price_clean}")
                    
                    except Exception as e:
                        st.write(f"Error processing element: {str(e)}")
                        continue
                
                if items:
                    break  # If we found items with this selector, stop trying others
        
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
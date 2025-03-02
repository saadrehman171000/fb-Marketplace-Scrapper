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
        
        # Use the public search endpoint
        search_url = f"https://www.facebook.com/marketplace/search/results/"
        
        # Headers to mimic a browser request
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
        }
        
        # Query parameters
        params = {
            'query': product,
            'exact': 'false',
            'latitude': None,
            'longitude': None,
            'radius': '60',
            'minPrice': str(min_price),
            'maxPrice': str(max_price),
            'categoryID': 'all',
            'sortBy': 'best_match',
            'daysSinceListed': 'all',
            'deliveryMethod': 'local_pick_up',
            'locationID': city_code_fb
        }
        
        st.write("Sending request...")
        st.write(f"URL: {search_url}")
        st.write(f"Parameters: {params}")
        
        items = []  # Initialize items list
        
        response = requests.get(search_url, headers=headers, params=params)
        
        st.write(f"Response status code: {response.status_code}")
        
        if response.status_code == 200:
            st.write("Response received successfully")
            
            # Parse the HTML response
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for marketplace items
            product_containers = soup.find_all('div', {'class': ['x1n2onr6', 'x6s0dn4']})
            st.write(f"Found {len(product_containers)} potential product containers")
            
            for container in product_containers:
                try:
                    # Try to find title and price
                    title_elem = container.find('span', {'class': 'x1lliihq'})
                    price_elem = container.find('span', {'class': 'x193iq5w'})
                    
                    if title_elem and price_elem:
                        title = title_elem.text
                        price_text = price_elem.text
                        price = ''.join(filter(str.isdigit, price_text))
                        price = int(price) if price else 0
                        
                        # Try to find link
                        link_elem = container.find('a')
                        link = f"https://www.facebook.com{link_elem['href']}" if link_elem else "#"
                        
                        items.append({
                            'title': title,
                            'price': price,
                            'link': link,
                            'city': city,
                            'search_term': product
                        })
                        st.write(f"Found item: {title} - ${price}")
                
                except Exception as e:
                    st.write(f"Error processing container: {str(e)}")
                    continue
            
            # Show sample of HTML for debugging
            st.write("Sample of response HTML:")
            st.code(response.text[:500])
            
        else:
            st.error(f"Request failed with status code: {response.status_code}")
            st.write("Response headers:", dict(response.headers))
            st.write("Response content:", response.text[:500])
        
        if items:
            df = pd.DataFrame(items)
            st.write("Scraped data preview:")
            st.write(df)
            return df, len(items)
        else:
            st.warning("No items found")
            return pd.DataFrame(), 0
            
    except Exception as e:
        st.error(f"Error during request: {str(e)}")
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
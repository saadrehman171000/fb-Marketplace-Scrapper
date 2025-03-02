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
import json
import requests

# Function to run the web scraping for exact matches
def scrape_facebook_marketplace_exact(city, product, min_price, max_price, city_code_fb):
    return scrape_facebook_marketplace(city, product, min_price, max_price, city_code_fb, exact=True)

# Function to run the web scraping for partial matches
def scrape_facebook_marketplace_partial(city, product, min_price, max_price, city_code_fb):
    return scrape_facebook_marketplace(city, product, min_price, max_price, city_code_fb, exact=False)

# Main scraping function with an exact match flag
def scrape_facebook_marketplace(city, product, min_price, max_price, city_code_fb, exact, sleep_time=3):
    try:
        st.info("Starting marketplace search...")
        
        # Use Facebook's mobile API
        base_url = f"https://m.facebook.com/marketplace/search/results/"
        
        # Headers to mimic a mobile browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_8_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/15E148 Safari/604.1',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-User': '?1',
            'Sec-Fetch-Dest': 'document',
            'Cache-Control': 'max-age=0'
        }
        
        # Query parameters
        params = {
            'query': product,
            'daysSinceListed': 'all',
            'sortBy': 'best_match',
            'exact': str(exact).lower(),
            'minPrice': str(min_price),
            'maxPrice': str(max_price),
            'location': city_code_fb,
            'radius': '60'
        }
        
        st.info("Sending request...")
        st.info(f"URL: {base_url}")
        st.info(f"Parameters: {params}")
        
        session = requests.Session()
        response = session.get(base_url, headers=headers, params=params)
        
        st.info(f"Response status: {response.status_code}")
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for marketplace items
            items = []
            
            # Try different selectors for marketplace items
            selectors = [
                'div[data-sigil="market-place-item"]',
                'div[data-ft*="marketplace"]',
                'a[href*="/marketplace/item/"]',
                'div._7g1d',  # Common Facebook marketplace item class
                'div[style*="border-radius: 8px"]'  # Item cards
            ]
            
            for selector in selectors:
                elements = soup.select(selector)
                st.info(f"Found {len(elements)} elements with selector: {selector}")
                
                if elements:
                    for element in elements:
                        try:
                            # Try to find title
                            title_elem = element.select_one('span._1qt3._a7o4,span._1qt3,div._1qt3')
                            title = title_elem.text.strip() if title_elem else None
                            
                            # Try to find price
                            price_elem = element.select_one('span._2zq0,span[data-sigil="price"]')
                            if price_elem:
                                price_text = price_elem.text.strip()
                                price = int(''.join(filter(str.isdigit, price_text)))
                            else:
                                continue
                            
                            # Try to find link
                            link = element.get('href')
                            if link and not link.startswith('http'):
                                link = f"https://www.facebook.com{link}"
                            
                            if title and price > 0:
                                items.append({
                                    'title': title,
                                    'price': price,
                                    'price_text': f"${price}",
                                    'location': city,
                                    'url': link or '#'
                                })
                                st.info(f"Found item: {title} - ${price}")
                        
                        except Exception as e:
                            st.warning(f"Error processing element: {str(e)}")
                            continue
                    
                    if items:
                        break
            
            st.info(f"Successfully extracted {len(items)} items")
            
            # Create DataFrame
            items_df = pd.DataFrame(items)
            if not items_df.empty:
                items_df = items_df[['title', 'price', 'price_text', 'location', 'url']]
            
            # Show sample of HTML for debugging
            st.info("Sample of response HTML:")
            st.code(response.text[:500])
            
            return items_df, len(items)
        
        else:
            st.error(f"Request failed with status {response.status_code}")
            st.info("Response headers:")
            st.write(dict(response.headers))
            return pd.DataFrame(), 0
            
    except Exception as e:
        st.error(f"Error during request: {str(e)}")
        return pd.DataFrame(), 0

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
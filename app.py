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
        
        # Use a different Facebook endpoint
        base_url = "https://www.facebook.com/marketplace/category/search"
        
        # Headers to mimic a real browser more closely
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Sec-Ch-Ua': '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0'
        }
        
        # Query parameters
        params = {
            'query': product,
            'latitude': '37.7749',  # San Francisco coordinates
            'longitude': '-122.4194',
            'radius': '60',
            'exact': str(exact).lower(),
            'minPrice': str(min_price),
            'maxPrice': str(max_price),
            'sortBy': 'best_match',
            'categoryID': 'all',
            'locationID': city_code_fb
        }
        
        st.info("Sending request...")
        st.info(f"URL: {base_url}")
        st.info(f"Parameters: {params}")
        
        session = requests.Session()
        
        # First, get the main page to get necessary cookies
        session.get("https://www.facebook.com/")
        
        # Then make the marketplace request
        response = session.get(base_url, headers=headers, params=params)
        
        st.info(f"Response status: {response.status_code}")
        st.info(f"Response encoding: {response.encoding}")
        
        if response.status_code == 200:
            # Ensure proper decoding
            response.encoding = 'utf-8'
            
            try:
                # Try to find JSON data in the response
                matches = re.findall(r'<script type="application/json".*?>(.*?)</script>', response.text)
                
                items = []
                for match in matches:
                    try:
                        data = json.loads(match)
                        st.info(f"Found JSON data: {str(data)[:200]}")
                        
                        # Look for marketplace items in the JSON
                        if isinstance(data, dict):
                            marketplace_data = data.get('marketplace', {}) or data.get('data', {}).get('marketplace_search', {})
                            
                            if marketplace_data:
                                listings = (
                                    marketplace_data.get('feed_units', []) or
                                    marketplace_data.get('search_results', []) or
                                    marketplace_data.get('items', [])
                                )
                                
                                for listing in listings:
                                    try:
                                        title = listing.get('title', '') or listing.get('marketplace_listing_title', '')
                                        price = listing.get('price', {}).get('amount', 0) or listing.get('listing_price', {}).get('amount', 0)
                                        item_id = listing.get('id', '')
                                        
                                        if title and price and item_id:
                                            items.append({
                                                'title': title,
                                                'price': float(price),
                                                'price_text': f"${price}",
                                                'location': city,
                                                'url': f"https://www.facebook.com/marketplace/item/{item_id}"
                                            })
                                            st.info(f"Found item: {title} - ${price}")
                                    except Exception as e:
                                        st.warning(f"Error processing listing: {str(e)}")
                                        continue
                    except json.JSONDecodeError:
                        continue
                
                st.info(f"Successfully extracted {len(items)} items")
                
                # Create DataFrame
                items_df = pd.DataFrame(items)
                if not items_df.empty:
                    items_df = items_df[['title', 'price', 'price_text', 'location', 'url']]
                
                # Show sample of response for debugging
                st.info("Sample of response text:")
                st.code(response.text[:500])
                
                return items_df, len(items)
            
            except Exception as e:
                st.error(f"Error processing response: {str(e)}")
                st.info("Response text sample:")
                st.code(response.text[:500])
                return pd.DataFrame(), 0
        
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
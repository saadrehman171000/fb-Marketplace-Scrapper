﻿import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import json
import time

def scrape_facebook_marketplace(city, product, min_price, max_price, city_code_fb, exact):
    headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_8_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148',
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.9',
        'X-FB-Friendly-Name': 'marketplace_search',
        'X-FB-LSD': '1',
        'X-ASBD-ID': '129477',
        'Origin': 'https://m.facebook.com',
        'Referer': 'https://m.facebook.com/marketplace/',
    }

    try:
        # Facebook's mobile API endpoint
        url = "https://m.facebook.com/api/graphql/"

        # Updated query variables for mobile API
        variables = {
            "params": {
                "marketplace_search": {
                    "query": product,
                    "location_id": city_code_fb,
                    "price_min": min_price,
                    "price_max": max_price
                }
            },
            "scale": 2
        }

        data = {
            "fb_api_caller_class": "RelayModern",
            "fb_api_req_friendly_name": "MarketplaceSearchQuery",
            "variables": json.dumps(variables),
            "doc_id": "5026154290794576"  # Mobile API query ID
        }

        st.info("Sending request to Facebook Mobile API...")
        response = requests.post(url, headers=headers, data=data)
        
        if response.status_code == 200:
            try:
                json_data = response.json()
                st.info("Processing response data...")
                
                items = []
                if 'data' in json_data and 'marketplace_search' in json_data['data']:
                    listings = json_data['data']['marketplace_search']['feed_units']
                    for listing in listings:
                        try:
                            story = listing.get('story')
                            if story:
                                items.append({
                                    'title': story.get('marketplace_listing_title', ''),
                                    'price': story.get('formatted_price', {}).get('price', 0),
                                    'price_text': story.get('formatted_price', {}).get('text', '$0'),
                                    'location': city,
                                    'url': f"https://www.facebook.com/marketplace/item/{story.get('id', '')}"
                                })
                        except Exception as e:
                            continue

                st.info(f"Found {len(items)} items")
                return pd.DataFrame(items), len(items)
            except Exception as e:
                st.error(f"Error processing response: {str(e)}")
                st.error(f"Response content: {response.text[:200]}...")  # Show first 200 chars of response
                return pd.DataFrame(), 0
        else:
            st.error(f"API request failed with status code: {response.status_code}")
            st.error(f"Response content: {response.text[:200]}...")  # Show first 200 chars of response
            return pd.DataFrame(), 0

    except Exception as e:
        st.error(f"Error during scraping: {str(e)}")
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
    st.session_state["scraped_data"] = None
    individual_files = []

    if not st.session_state["marketplaces"]:
        st.error("Please add at least one marketplace to scrape data.")
    else:
        combined_df = pd.DataFrame()
        for marketplace in st.session_state["marketplaces"]:
            with st.spinner(f"Scraping data for {marketplace['city']}..."):
                items_df, total_links = scrape_facebook_marketplace(
                    marketplace["city"],
                    marketplace["product"],
                    marketplace["min_price"],
                    marketplace["max_price"],
                    marketplace["city_code_fb"],
                    exact=True
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

import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import json
import time
import io
import zipfile

def scrape_facebook_marketplace(city, product, min_price, max_price, city_code_fb, exact):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Cache-Control': 'max-age=0',
        'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Upgrade-Insecure-Requests': '1',
        'Cookie': 'locale=en_US; c_user=guest; presence=guest'
    }

    try:
        session = requests.Session()
        
        # First, get CSRF token
        init_response = session.get('https://www.facebook.com', headers=headers)
        if init_response.status_code == 200:
            st.info("Got initial Facebook page...")
            
            # Try to extract CSRF token
            content = init_response.text
            csrf_start = content.find('"async_get_token":"') + 18
            if csrf_start > 18:
                csrf_end = content.find('"', csrf_start)
                csrf_token = content[csrf_start:csrf_end]
                headers['X-Fb-Friendly-Name'] = 'CometMarketplaceSearchContentPaginationQuery'
                headers['X-Fb-Lsd'] = csrf_token
            
            # Now try the marketplace API
            api_url = "https://www.facebook.com/api/graphql/"
            variables = {
                "count": 24,
                "params": {
                    "bqf": {
                        "callsite": "COMMERCE_MKTPLACE_WWW",
                        "query": product,
                        "regionid": city_code_fb,
                        "filters": [
                            {"price_lower_bound": min_price},
                            {"price_upper_bound": max_price}
                        ]
                    }
                }
            }
            
            data = {
                "doc_id": "7711610262190251",
                "variables": json.dumps(variables),
                "fb_dtsg": csrf_token
            }
            
            st.info("Sending marketplace search request...")
            response = session.post(api_url, headers=headers, data=data)
            
            if response.status_code == 200:
                try:
                    json_data = response.json()
                    items = []
                    
                    # Try different paths to find listings
                    paths = [
                        ['data', 'marketplace_search', 'feed_units'],
                        ['data', 'marketplace_search', 'edges'],
                        ['data', 'marketplace_search', 'results']
                    ]
                    
                    for path in paths:
                        current = json_data
                        for key in path:
                            if isinstance(current, dict) and key in current:
                                current = current[key]
                            else:
                                current = None
                                break
                        
                        if current and isinstance(current, list):
                            for item in current:
                                try:
                                    listing = item.get('node', item)
                                    items.append({
                                        'title': listing.get('title', ''),
                                        'price': listing.get('price', {}).get('amount', 0),
                                        'price_text': f"${listing.get('price', {}).get('amount', 0)}",
                                        'location': city,
                                        'url': f"https://www.facebook.com/marketplace/item/{listing.get('id', '')}"
                                    })
                                except:
                                    continue
                            
                            if items:
                                break
                    
                    st.info(f"Found {len(items)} items")
                    return pd.DataFrame(items), len(items)
                    
                except Exception as e:
                    st.error(f"Error parsing response: {str(e)}")
            else:
                st.error(f"API request failed: {response.status_code}")
                
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
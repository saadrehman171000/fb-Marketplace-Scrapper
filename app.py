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
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Dest': 'document',
        'Upgrade-Insecure-Requests': '1',
        'Connection': 'keep-alive',
    }

    try:
        # First get a session cookie
        session = requests.Session()
        
        # Try different search endpoints
        search_urls = [
            f"https://www.facebook.com/marketplace/search?query={product}&exact=false&minPrice={min_price}&maxPrice={max_price}&latitude=34.0522&longitude=-118.2437",
            f"https://www.facebook.com/marketplace/{city_code_fb}/search?query={product}&exact=false&minPrice={min_price}&maxPrice={max_price}",
            f"https://www.facebook.com/marketplace/category/search?query={product}&exact=false&minPrice={min_price}&maxPrice={max_price}&region_id={city_code_fb}"
        ]

        items = []
        for url in search_urls:
            try:
                st.info(f"Trying URL: {url}")
                
                # Get initial page to get cookies
                initial_response = session.get("https://www.facebook.com/marketplace/", headers=headers)
                if initial_response.status_code == 200:
                    st.info("Got initial session...")
                
                # Now try the search
                response = session.get(url, headers=headers)
                
                if response.status_code == 200:
                    st.info("Got search response, looking for data...")
                    
                    # Look for marketplace data in the HTML
                    content = response.text
                    
                    # Try to find the JSON data embedded in the page
                    data_start = content.find('"marketplace_search":{')
                    if data_start != -1:
                        data_end = content.find('</script>', data_start)
                        json_str = content[data_start:data_end]
                        
                        # Extract listing data
                        listing_start = json_str.find('"listing":{')
                        while listing_start != -1:
                            try:
                                listing_end = json_str.find('}', listing_start)
                                listing_data = json_str[listing_start:listing_end+1]
                                
                                # Parse individual listing
                                title_start = listing_data.find('"title":"') + 9
                                title_end = listing_data.find('",', title_start)
                                title = listing_data[title_start:title_end]
                                
                                price_start = listing_data.find('"price":{"amount":') + 16
                                price_end = listing_data.find('}', price_start)
                                price = listing_data[price_start:price_end]
                                
                                items.append({
                                    'title': title,
                                    'price': float(price) if price.isdigit() else 0,
                                    'price_text': f"${price}",
                                    'location': city,
                                    'url': url
                                })
                                
                                listing_start = json_str.find('"listing":{', listing_end)
                            except:
                                break
                    
                    if items:
                        break
                        
            except Exception as e:
                st.warning(f"Failed with URL {url}: {str(e)}")
                continue

        st.info(f"Found {len(items)} items")
        return pd.DataFrame(items), len(items)

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
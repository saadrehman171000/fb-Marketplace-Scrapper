import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import json
import time
import io
import zipfile
from urllib.parse import quote
from dotenv import load_dotenv
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

load_dotenv()  # Load environment variables from .env file

def init_session_state():
    if 'driver' not in st.session_state:
        st.session_state.driver = None
        st.session_state.logged_in = False

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    return webdriver.Chrome(options=chrome_options)

def facebook_login(email, password):
    try:
        if not st.session_state.driver:
            st.session_state.driver = setup_driver()
        
        driver = st.session_state.driver
        driver.get('https://www.facebook.com')
        
        # Wait for email field and enter email
        email_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "email"))
        )
        email_field.send_keys(email)
        
        # Enter password
        password_field = driver.find_element(By.ID, "pass")
        password_field.send_keys(password)
        
        # Click login button
        login_button = driver.find_element(By.NAME, "login")
        login_button.click()
        
        # Wait for successful login
        time.sleep(5)  # Wait for login to complete
        
        if "home" in driver.current_url.lower():
            st.session_state.logged_in = True
            st.success("Successfully logged in to Facebook!")
            return True
            
        return False
        
    except Exception as e:
        st.error(f"Login error: {str(e)}")
        return False

def scrape_facebook_marketplace(city, product, min_price, max_price, city_code_fb, exact):
    if not st.session_state.logged_in:
        if not auto_login():
            st.error("No active Facebook session. Please log in first.")
            return pd.DataFrame(), 0
    
    try:
        driver = st.session_state.driver
        marketplace_url = f"https://www.facebook.com/marketplace/{city_code_fb}/search?query={product}&minPrice={min_price}&maxPrice={max_price}"
        driver.get(marketplace_url)
        
        # Add your scraping logic here using Selenium
        # This is a placeholder - you'll need to implement the actual scraping
        time.sleep(5)  # Wait for page to load
        
        # Return empty DataFrame for now
        return pd.DataFrame(), 0
        
    except Exception as e:
        st.error(f"Error during scraping: {str(e)}")
        return pd.DataFrame(), 0

def auto_login():
    email = os.getenv('FACEBOOK_EMAIL')
    password = os.getenv('FACEBOOK_PASSWORD')
    
    if email and password and not st.session_state.logged_in:
        return facebook_login(email, password)
    return False

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

# Initialize session state
init_session_state()

# Try auto-login before rendering anything
auto_login()

# Only show login form if auto-login failed
with st.sidebar:
    st.header("Facebook Login")
    
    if not st.session_state.logged_in:
        with st.form("login_form"):
            email = st.text_input("Email", value=os.getenv('FACEBOOK_EMAIL', ''), type="default")
            password = st.text_input("Password", value=os.getenv('FACEBOOK_PASSWORD', ''), type="password")
            login_button = st.form_submit_button("Login")
            
            if login_button and email and password:
                session = facebook_login(email, password)
                if session:
                    st.session_state.fb_session = session
                    st.session_state.logged_in = True
                    st.rerun()
    else:
        st.success("Logged in successfully!")
        if st.button("Logout"):
            st.session_state.fb_session = None
            st.session_state.logged_in = False
            st.rerun()

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
    if 'fb_session' not in st.session_state:
        st.error("Please log in to Facebook first")
    else:
        # Use the authenticated session for scraping
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
import streamlit as st
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import pandas as pd
import time
import re
from io import BytesIO

class JustdialSeleniumScraper:
    def __init__(self):
        self.results = []
        self.driver = None
    
    def setup_driver(self):
        """Setup Chrome driver with options"""
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        try:
            self.driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=chrome_options
            )
            return True
        except Exception as e:
            st.error(f"Error setting up Chrome driver: {e}")
            return False
    
    def clean_phone(self, phone):
        """Clean phone number"""
        if phone:
            cleaned = re.sub(r'[^\d,]', '', phone)
            return cleaned if cleaned else 'N/A'
        return 'N/A'
    
    def extract_gstin(self, detail_url):
        """Extract GSTIN from detail page"""
        try:
            self.driver.get(detail_url)
            time.sleep(2)
            
            # Wait for page to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Look for GSTIN
            try:
                gstin_elements = self.driver.find_elements(By.XPATH, "//div[contains(text(), 'GSTIN')]")
                if gstin_elements:
                    parent = gstin_elements[0].find_element(By.XPATH, "./..")
                    gstin_value = parent.find_elements(By.CLASS_NAME, "dtl_infotext")
                    if gstin_value:
                        return gstin_value[0].text.strip()
            except:
                pass
            
            # Alternative: search in page source
            page_source = self.driver.page_source
            gstin_match = re.search(r'\b\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}[Z]{1}[A-Z\d]{1}\b', page_source)
            if gstin_match:
                return gstin_match.group()
            
            return 'N/A'
        except Exception as e:
            return 'N/A'
    
    def scrape_search(self, location, search_term, max_pages=3, progress_callback=None, include_gstin=True):
        """Scrape Justdial using Selenium"""
        self.results = []
        
        if not self.setup_driver():
            return 0
        
        try:
            search_formatted = search_term.replace(' ', '-').lower()
            location_formatted = location.replace(' ', '-').lower()
            
            total_extracted = 0
            
            for page in range(1, max_pages + 1):
                try:
                    if page == 1:
                        url = f"https://www.justdial.com/{location_formatted}/{search_formatted}"
                    else:
                        url = f"https://www.justdial.com/{location_formatted}/{search_formatted}/page-{page}"
                    
                    if progress_callback:
                        progress_callback(f"📄 Scraping page {page}/{max_pages}...", page / max_pages * 0.3)
                    
                    self.driver.get(url)
                    time.sleep(3)
                    
                    # Wait for results to load
                    try:
                        WebDriverWait(self.driver, 10).until(
                            EC.presence_of_element_located((By.TAG_NAME, "h3"))
                        )
                    except:
                        if progress_callback:
                            progress_callback(f"⚠️ Page {page} took too long to load", page / max_pages * 0.3)
                        continue
                    
                    # Scroll to load all content
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(2)
                    
                    # Find company listings
                    company_elements = self.driver.find_elements(By.XPATH, "//h3[contains(@class, 'resultbox_title_anchor')]")
                    
                    if not company_elements:
                        if progress_callback:
                            progress_callback(f"⚠️ No listings found on page {page}", page / max_pages * 0.3)
                        break
                    
                    for idx, company_elem in enumerate(company_elements):
                        try:
                            company_name = company_elem.text.strip()
                            
                            if not company_name:
                                continue
                            
                            # Get parent container
                            parent = company_elem.find_element(By.XPATH, "./ancestor::li[1] | ./ancestor::div[contains(@class, 'resultbox')][1]")
                            
                            # Extract phone number
                            phone = 'N/A'
                            try:
                                phone_elements = parent.find_elements(By.XPATH, ".//span[contains(@class, 'callcontent') or contains(@class, 'callNowAnchor')]")
                                if phone_elements:
                                    phone = phone_elements[0].text.strip()
                                else:
                                    # Try to find any 10-digit number
                                    parent_text = parent.text
                                    phone_match = re.search(r'\b\d{10}\b', parent_text)
                                    if phone_match:
                                        phone = phone_match.group()
                            except:
                                pass
                            
                            # Extract address
                            address = 'N/A'
                            try:
                                address_elements = parent.find_elements(By.XPATH, ".//span[contains(@class, 'address') or contains(@class, 'mrehover')]")
                                if address_elements:
                                    address = address_elements[0].text.strip()
                            except:
                                pass
                            
                            # Extract GSTIN if requested
                            gstin = 'N/A'
                            if include_gstin:
                                try:
                                    link = company_elem.find_element(By.XPATH, "./ancestor::a[1]")
                                    detail_url = link.get_attribute('href')
                                    
                                    if detail_url and 'BZDET' in detail_url:
                                        if progress_callback:
                                            progress_callback(f"🔍 Fetching GSTIN for {company_name[:30]}...", 
                                                            (page - 1 + (idx + 1) / len(company_elements)) / max_pages * 0.3 + 0.3)
                                        
                                        gstin = self.extract_gstin(detail_url)
                                        time.sleep(1)
                                except:
                                    pass
                            
                            self.results.append({
                                'Company Name': company_name,
                                'Phone Number': self.clean_phone(phone),
                                'GSTIN': gstin,
                                'Address': address,
                                'Location': location,
                                'Search Term': search_term
                            })
                            total_extracted += 1
                            
                        except Exception as e:
                            continue
                    
                    time.sleep(2)
                    
                except Exception as e:
                    if progress_callback:
                        progress_callback(f"❌ Error on page {page}: {str(e)}", page / max_pages * 0.3)
                    break
            
            return total_extracted
            
        finally:
            if self.driver:
                self.driver.quit()

# Streamlit App
def main():
    st.set_page_config(
        page_title="Justdial Scraper",
        page_icon="📞",
        layout="wide"
    )
    
    st.title("📞 Justdial Business Scraper")
    st.markdown("Extract company names, phone numbers, GSTIN, and addresses from Justdial")
    
    # Important notice
    st.info("🔧 **Using Selenium for better reliability.** First run may take time to download Chrome driver.")
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Settings")
        
        location = st.text_input(
            "📍 Location",
            placeholder="e.g., Mumbai, Delhi, Bangalore",
            help="Enter the city or area to search in"
        )
        
        search_term = st.text_input(
            "🔍 Search Term",
            placeholder="e.g., timber suppliers, roofing sheets",
            help="What type of business are you looking for?"
        )
        
        max_pages = st.slider(
            "📄 Max Pages",
            min_value=1,
            max_value=10,
            value=3,
            help="Number of pages to scrape (more pages = more time)"
        )
        
        include_gstin = st.checkbox(
            "Include GSTIN",
            value=False,
            help="Extract GSTIN (much slower but more data)"
        )
        
        st.markdown("---")
        st.markdown("### ⚠️ Important Notes")
        st.markdown("""
        - Uses Selenium for reliability
        - First run downloads driver
        - GSTIN extraction is very slow
        - Be patient during scraping
        """)
    
    # Main content
    col1, col2 = st.columns([2, 1])
    
    with col1:
        scrape_button = st.button("🚀 Start Scraping", type="primary", use_container_width=True)
    
    with col2:
        if 'df' in st.session_state and st.session_state.df is not None:
            if st.button("🗑️ Clear Results", use_container_width=True):
                st.session_state.df = None
                st.rerun()
    
    # Initialize session state
    if 'df' not in st.session_state:
        st.session_state.df = None
    
    # Scraping logic
    if scrape_button:
        if not location or not search_term:
            st.error("⚠️ Please enter both location and search term!")
        else:
            scraper = JustdialSeleniumScraper()
            
            # Progress tracking
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            def update_progress(message, progress):
                status_text.text(message)
                progress_bar.progress(min(progress, 1.0))
            
            # Start scraping
            try:
                with st.spinner("🔄 Setting up browser and scraping..."):
                    total = scraper.scrape_search(
                        location, 
                        search_term, 
                        max_pages,
                        progress_callback=update_progress,
                        include_gstin=include_gstin
                    )
                
                progress_bar.progress(1.0)
                status_text.text("✅ Scraping completed!")
                
                if scraper.results:
                    df = pd.DataFrame(scraper.results)
                    df = df.drop_duplicates(subset=['Phone Number'], keep='first')
                    
                    st.session_state.df = df
                    
                    st.success(f"✅ Successfully scraped {len(df)} unique businesses!")
                else:
                    st.warning("⚠️ No results found. Try different search terms.")
                    
            except Exception as e:
                st.error(f"❌ Error during scraping: {str(e)}")
                st.info("💡 Try: reducing max pages, checking internet connection, or disabling GSTIN")
    
    # Display results
    if st.session_state.df is not None:
        df = st.session_state.df
        
        st.markdown("---")
        st.header("📊 Results")
        
        # Metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Businesses", len(df))
        with col2:
            st.metric("With Phone", len(df[df['Phone Number'] != 'N/A']))
        with col3:
            st.metric("With GSTIN", len(df[df['GSTIN'] != 'N/A']))
        with col4:
            st.metric("With Address", len(df[df['Address'] != 'N/A']))
        
        # Data table
        st.dataframe(df, use_container_width=True, height=400)
        
        # Download section
        st.markdown("---")
        st.header("💾 Download Data")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Excel download
            buffer = BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Justdial Data')
            
            st.download_button(
                label="📥 Download Excel",
                data=buffer.getvalue(),
                file_name=f"justdial_{search_term.replace(' ', '_')}_{location.replace(' ', '_')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        
        with col2:
            # CSV download
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download CSV",
                data=csv,
                file_name=f"justdial_{search_term.replace(' ', '_')}_{location.replace(' ', '_')}.csv",
                mime="text/csv",
                use_container_width=True
            )

if __name__ == "__main__":
    main()

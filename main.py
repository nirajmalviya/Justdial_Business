import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
from io import BytesIO


class JustdialScraper:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        self.results = []

    def clean_phone(self, phone):
        """Clean phone number by removing extra characters"""
        if phone:
            cleaned = re.sub(r'[^\d,]', '', phone)
            return cleaned if cleaned else 'N/A'
        return 'N/A'

    def extract_gstin(self, detail_url):
        """Extract GSTIN from detail page"""
        try:
            response = requests.get(detail_url, headers=self.headers, timeout=10)

            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')

                # Look for GSTIN in the detail page
                gstin_elem = soup.find('div', class_=re.compile(r'dtl_labeltext'),
                                       string=re.compile(r'GSTIN', re.IGNORECASE))

                if gstin_elem:
                    parent = gstin_elem.find_parent('li')
                    if parent:
                        gstin_value = parent.find('div', class_=re.compile(r'dtl_infotext'))
                        if gstin_value:
                            return gstin_value.get_text(strip=True)

                # Alternative method: search for GSTIN pattern
                gstin_match = re.search(r'\b\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}[Z]{1}[A-Z\d]{1}\b', soup.get_text())
                if gstin_match:
                    return gstin_match.group()

            return 'N/A'

        except Exception as e:
            return 'N/A'

    def scrape_search(self, location, search_term, max_pages=3, progress_callback=None, include_gstin=True):
        """Scrape Justdial for given location and search term"""
        self.results = []

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
                    progress_callback(f"📄 Scraping page {page}/{max_pages}...", page / max_pages * 0.5)

                response = requests.get(url, headers=self.headers, timeout=15)

                if response.status_code != 200:
                    break

                soup = BeautifulSoup(response.content, 'html.parser')

                # Find company elements
                company_elements = soup.find_all('h3', class_=re.compile(r'resultbox_title_anchor'))
                if not company_elements:
                    company_elements = soup.find_all(class_=re.compile(r'resultbox.*title'))
                if not company_elements:
                    company_elements = soup.find_all('span', class_=lambda x: x and 'jcn' in x)

                extracted_count = 0

                for idx, company_elem in enumerate(company_elements):
                    try:
                        company_name = company_elem.get_text(strip=True)

                        parent = company_elem.find_parent('li')
                        if not parent:
                            parent = company_elem.find_parent('div', class_=re.compile(r'resultbox|store|listing'))
                        if not parent:
                            parent = company_elem.find_parent('article')

                        if parent:
                            # Extract phone
                            phone_elem = parent.find('span', class_=re.compile(r'callcontent|callNowAnchor'))
                            if not phone_elem:
                                phone_elem = parent.find('span', class_=re.compile(r'call'))
                            if not phone_elem:
                                phone_elem = parent.find('span', string=re.compile(r'\d{10}'))
                            if not phone_elem:
                                phone_text = parent.get_text()
                                phone_match = re.search(r'\b\d{10}\b', phone_text)
                                phone = phone_match.group() if phone_match else 'N/A'
                            else:
                                phone = phone_elem.get_text(strip=True)

                            # Extract address
                            address_elem = parent.find('span',
                                                       class_=re.compile(r'mrehover|address|resultbox__address'))
                            if not address_elem:
                                address_elem = parent.find('p', class_=re.compile(r'address'))
                            address = address_elem.get_text(strip=True) if address_elem else 'N/A'

                            # Extract GSTIN
                            gstin = 'N/A'
                            if include_gstin:
                                link_elem = company_elem.find_parent('a')
                                if link_elem and link_elem.get('href'):
                                    detail_link = link_elem.get('href')
                                    if not detail_link.startswith('http'):
                                        detail_link = 'https://www.justdial.com' + detail_link

                                    if progress_callback:
                                        progress_callback(f"🔍 Fetching GSTIN for {company_name}...",
                                                          (page - 1 + (idx + 1) / len(
                                                              company_elements)) / max_pages * 0.5 + 0.5)

                                    gstin = self.extract_gstin(detail_link)
                                    time.sleep(1)

                            self.results.append({
                                'Company Name': company_name,
                                'Phone Number': self.clean_phone(phone),
                                'GSTIN': gstin,
                                'Address': address,
                                'Location': location,
                                'Search Term': search_term
                            })
                            extracted_count += 1

                    except Exception as e:
                        continue

                total_extracted += extracted_count
                time.sleep(2)

            except Exception as e:
                break

        return total_extracted


# Streamlit App
def main():
    st.set_page_config(
        page_title="Justdial Scraper",
        page_icon="📞",
        layout="wide"
    )

    st.title("📞 Justdial Business Scraper")
    st.markdown("Extract company names, phone numbers, GSTIN, and addresses from Justdial")

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
            value=True,
            help="Extract GSTIN (slower but more data)"
        )

        st.markdown("---")
        st.markdown("### ⚠️ Important Notes")
        st.markdown("""
        - Scraping may take time
        - GSTIN extraction is slower
        - Respect Justdial's ToS
        - Results may vary
        """)

    # Main content
    col1, col2 = st.columns([2, 1])

    with col1:
        scrape_button = st.button("🚀 Start Scraping", type="primary", use_container_width=True)

    with col2:
        if 'df' in st.session_state and st.session_state.df is not None:
            if st.button("🗑️ Clear Results", use_container_width=True):
                st.session_state.df = None
                st.session_state.scraper = None
                st.rerun()

    # Initialize session state
    if 'df' not in st.session_state:
        st.session_state.df = None
    if 'scraper' not in st.session_state:
        st.session_state.scraper = None

    # Scraping logic
    if scrape_button:
        if not location or not search_term:
            st.error("⚠️ Please enter both location and search term!")
        else:
            scraper = JustdialScraper()

            # Progress tracking
            progress_bar = st.progress(0)
            status_text = st.empty()

            def update_progress(message, progress):
                status_text.text(message)
                progress_bar.progress(min(progress, 1.0))

            # Start scraping
            with st.spinner("Scraping in progress..."):
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
                st.session_state.scraper = scraper

                st.success(f"✅ Successfully scraped {len(df)} unique businesses!")
            else:
                st.warning("⚠️ No results found. Try different search terms or check your internet connection.")

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

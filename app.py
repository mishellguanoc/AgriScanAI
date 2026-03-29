import streamlit as st
from components.header import show_header
from components.analysis import analysis_page
from components.assistant import assistant_page
from components.map_view import map_page, get_cached_map_html
from utils.db_manager import fetch_all_records

st.set_page_config(
    page_title="AgriScan AI",
    layout="wide"
)

# [STARTUP] Pre-load database cache and pre-render the map HTML
initial_data = fetch_all_records()
if not initial_data.empty:
    get_cached_map_html(initial_data)

show_header()

tabs = st.tabs([
    "Crop Analysis",
    "Agronomic Assistant",
    "Epidemiological Map"
])

with tabs[0]:
    analysis_page()

with tabs[1]:
    assistant_page()

with tabs[2]:
    map_page()
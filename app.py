import streamlit as st
from components.header import show_header
from components.analysis import analysis_page
from components.assistant import assistant_page
from components.map_view import map_page

st.set_page_config(
    page_title="AgriScan AI",
    layout="wide"
)

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
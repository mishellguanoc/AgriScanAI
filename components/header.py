import streamlit as st
from PIL import Image

def show_header():

    col1, col2 = st.columns([1,5])

    with col1:
        logo = Image.open("assets/logo.png")
        st.image(logo, width=100)

    with col2:
        st.title("AgriScan AI")
        st.caption("Distributed Agricultural Monitoring Platform")
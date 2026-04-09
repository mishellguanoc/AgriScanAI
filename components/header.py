import streamlit as st
from PIL import Image


def show_header():

    # ===== CONTENEDOR PRINCIPAL =====
    with st.container():

        col1, col2 = st.columns([1, 6])

        # ===== LOGO =====
        with col1:
            logo = Image.open("assets/logo.png")
            st.image(logo, width=80)

        # ===== TITULOS =====
        with col2:
            st.markdown("""
                <div style="display:flex; flex-direction:column; justify-content:center;">
                    <h1 style="margin-bottom:0; font-size:32px;">
                        AgriScan AI
                    </h1>
                    <p style="margin-top:5px; color: gray; font-size:14px;">
                        Distributed Agricultural Monitoring Platform
                    </p>
                </div>
            """, unsafe_allow_html=True)

    # ===== DIVISOR PRO =====
    st.markdown("""
        <hr style="
            margin-top: 10px;
            margin-bottom: 25px;
            border: none;
            height: 1px;
            background: linear-gradient(to right, transparent, #2E7D32, transparent);
        ">
    """, unsafe_allow_html=True)
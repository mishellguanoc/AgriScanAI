import streamlit as st


def show_header():

    # ===== CONTENEDOR PRINCIPAL =====
    with st.container():
        # Aumentamos el ratio del logo y el espaciado general
        col1, col2 = st.columns([1.2, 7], vertical_alignment="center")

        # ===== LOGO =====
        with col1:
            st.image("assets/AgriScanLogoBW.svg", use_container_width=True)

        # ===== TITULOS =====
        with col2:
            st.markdown("""
                <div style="display:flex; flex-direction:column; justify-content:center; padding-left:30px; padding-top:10px; padding-bottom:10px;">
                    <h1 style="margin-bottom:5px; font-size:48px; line-height:1; letter-spacing:-0.04em;">
                        AgriScan AI
                    </h1>
                    <p style="margin-top:5px; color: #888; font-size:18px; font-weight:500; letter-spacing:-0.01em;">
                        Distributed Agricultural Monitoring Platform
                    </p>
                </div>
            """, unsafe_allow_html=True)

    # ===== DIVISOR PREMIUM (MÁS GRUESO) =====
    st.markdown("""
        <div style="
            height: 3px;
            background: linear-gradient(to right, transparent, #2E7D32, #1E88E5, transparent);
            margin: 30px 0 50px 0;
            opacity: 0.8;
        "></div>
    """, unsafe_allow_html=True)
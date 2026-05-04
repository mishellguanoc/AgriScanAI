import streamlit as st


def show_header():

    # ===== CONTENEDOR PRINCIPAL =====
    with st.container():
        col1, col2 = st.columns([0.5, 3], vertical_alignment="center")


        # ===== LOGO =====
        with col1:
            st.image("assets/logo2.svg", use_container_width=True)


        # ===== TITULOS =====
        with col2:
            st.markdown("""
                <div style="display:flex; flex-direction:column; justify-content:center; padding-left:20px; padding-top:2px; padding-bottom:2px;">
                    <h1 style="margin-bottom:2px; font-size:46px; line-height:1; letter-spacing:-0.03em;">
                        AgriScan AI
                    </h1>
                    <p style="margin-top:2px; color: #888; font-size:22px; font-weight:500; letter-spacing:-0.01em;">
                        Distributed Agricultural Monitoring Platform
                    </p>
                </div>
            """, unsafe_allow_html=True)

    # ===== DIVISOR =====
    st.markdown("""
        <div style="
            height: 2px;
            background: linear-gradient(to right, transparent, #2E7D32, #1E88E5, transparent);
            margin: 12px 0 24px 0;
            opacity: 0.8;
        "></div>
    """, unsafe_allow_html=True)
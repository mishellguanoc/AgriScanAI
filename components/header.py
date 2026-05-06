import streamlit as st


def show_header():

    # ===== CONTENEDOR PRINCIPAL =====
    with st.container():
        col1, col2 = st.columns([0.55, 3.45], vertical_alignment="center")


        # ===== LOGO =====
        with col1:
            import base64
            with open("assets/logo_verde.svg", "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            st.markdown(
                f'<img src="data:image/svg+xml;base64,{b64}" '
                f'style="width:100%; '
                f'transition:transform 0.3s ease; display:block;" '
                f'onmouseover="this.style.transform=\'scale(1.05)\'" '
                f'onmouseout="this.style.transform=\'scale(1)\'"/>', 
                unsafe_allow_html=True
            )


        # ===== TITULOS =====
        with col2:
            st.markdown("""
                <div style="display:flex; flex-direction:column; justify-content:center; padding-left:20px; padding-top:2px; padding-bottom:2px;">
                    <h1 style="margin-bottom:2px; font-size:clamp(1.8rem, 6.5vw, 56px); line-height:1; letter-spacing:-0.03em;">
                        AgriScan AI
                    </h1>
                    <p style="margin-top:2px; color: #888; font-size:clamp(0.85rem, 3.5vw, 22px); font-weight:500; letter-spacing:-0.01em;">
                        Distributed Agricultural Monitoring Platform
                    </p>
                </div>
            """, unsafe_allow_html=True)

    # ===== DIVISOR =====
    st.markdown("""
        <style>
        @media screen and (max-width: 768px) {
            .agriscan-header-divider { margin: 8px 0 12px 0 !important; }
        }
        </style>
        <div class="agriscan-header-divider" style="
            height: 2px;
            background: linear-gradient(to right, transparent, #2E7D32, #1B5E20, transparent);
            margin: 12px 0 24px 0;
            opacity: 0.8;
        "></div>
    """, unsafe_allow_html=True)
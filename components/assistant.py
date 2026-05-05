"""
components/assistant.py
Asistente agronómico con RAG (FAISS + Groq/LLaMA 3).
"""

import streamlit as st
from rag.core import load_faiss_index, ask
from utils.db_manager import fetch_diagnosis_context

@st.cache_resource
def _get_faiss():
    return load_faiss_index()


def assistant_page():

# ── Estilos  ───────────────────
    st.markdown("""
        <style>
        /* Ajustar altura del input text */
        .stTextInput input {
            height: 52px !important;
            line-height: 2 !important;
            font-size: 1rem !important;
            padding: 1.2rem 20px 3rem 5px !important; /* top, right, bottom, left */
        }

        /* Ajustar altura y padding del botón Send */
        div[data-testid="column"]:nth-of-type(2) .stButton button {
            height: 52px !important;
            padding: 0rem 20px 0.5rem 5px !important; /* top, right, bottom, left */
            font-size: 5rem !important;
            line-height: 1 !important;
            background-color: #6FAF6A !important;
            color: white !important;
            border: none !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
        }

        div[data-testid="column"]:nth-of-type(2) .stButton button:hover {
            background-color: #0a4425 !important;
            color: white !important;
        }

        /* Alinear columnas en la parte inferior */
        div[data-testid="column"]:nth-of-type(1),
        div[data-testid="column"]:nth-of-type(2) {
            display: flex !important;
            align-items: flex-end !important;
        }

        /* Quitar margen extra */
        .stTextInput {
            margin-bottom: 0 !important;
        }
        </style>
        """, unsafe_allow_html=True)

    # ── Wrapper con padding lateral ────────────────────────────────────────
    _, col_main, _ = st.columns([0.08, 0.84, 0.08])

    with col_main:

        # Título compacto
        st.markdown("### Agronomic Assistant")

        # Badge del modelo
        st.markdown(
            '<a href="https://console.groq.com/docs/models" target="_blank" style="font-size:20px; font-weight:bold; color:#6FAF6A; text-decoration:underline;">'
            'Powered by LLaMA 3.3-70b via Groq'
            '</a>',
            unsafe_allow_html=True
        )

        # ── Cargar FAISS ───────────────────────────────────────────────────
        try:
            faiss_manager = _get_faiss()
        except Exception as e:
            st.error(f"⚠️ Could not load knowledge base: {e}")
            st.info("Run `scripts/build_kb.py` to generate the index.")
            return

        # ── Session state ──────────────────────────────────────────────────
        if "rag_messages" not in st.session_state:
            st.session_state.rag_messages = []

        # ── Controles: perfil + clear ──────────────────────────────────────
        col_role, col_clear = st.columns([4, 1])
        with col_role:
            role = st.radio(
                "Profile",
                ["beginner", "expert"],
                format_func=lambda x: "👨‍🌾 Farmer" if x == "beginner" else "👨‍🔬 Agronomist",
                horizontal=True,
                label_visibility="collapsed"
            )
        with col_clear:
            if st.button("🗑 Clear", use_container_width=True):
                st.session_state.rag_messages = []
                st.rerun()

        st.divider()

        # ── Historial ──────────────────────────────────────────────────────
        chat_container = st.container(height=380)
        with chat_container:
            if not st.session_state.rag_messages:
                st.markdown(
                    "<div style='text-align:center; color:#3a3737; padding-top:60px; font-size:2rem;'>"
                    "<b>Start by asking about a crop disease,<br>"
                    "treatment or prevention method</b>"
                    "</div>",
                    unsafe_allow_html=True
                )
            for msg in st.session_state.rag_messages:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])
                    if msg.get("sources"):
                        st.caption("📄 " + " · ".join(msg["sources"]))

        # ── Input con alturas iguales ──────────────────────────────────────
        col_input, col_btn = st.columns([5, 1])
        with col_input:
            query = st.text_input(
            "query",
            placeholder="🌱 e.g. ¿Qué síntomas tiene el tizón tardío en papa?",
            label_visibility="collapsed",
            key="rag_input_field"
    )

        with col_btn:
            # Quitar type="primary" para que tome los estilos personalizados
            send = st.button("➤", use_container_width=True)

        # ── Procesar ───────────────────────────────────────────────────────
        if send and query.strip():
            st.session_state.rag_messages.append({"role": "user", "content": query})

            history = [
                {"role": m["role"], "content": m["content"]}
                for m in st.session_state.rag_messages[-6:]
                if m["role"] in ("user", "assistant")
            ]

            with st.spinner("Consulting knowledge base..."):
                try:
                    db_context = fetch_diagnosis_context()
                    result = ask(
                        query=query,
                        faiss_manager=faiss_manager,
                        expertise=role,
                        history=history,
                        db_context=db_context,
                    )
                    st.session_state.rag_messages.append({
                        "role": "assistant",
                        "content": result["answer"],
                        "sources": result["sources"]
                    })
                except Exception as e:
                    st.session_state.rag_messages.append({
                        "role": "assistant",
                        "content": f"⚠️ Error: {e}",
                        "sources": []
                    })
            st.rerun()
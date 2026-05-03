"""
components/assistant.py
Asistente agronómico con RAG (FAISS + Groq/LLaMA 3).
Reemplaza el placeholder original por respuestas reales basadas en documentos.
"""

import streamlit as st
from rag.core import load_faiss_index, ask


@st.cache_resource
def _get_faiss():
    """Carga el índice FAISS una sola vez para toda la sesión."""
    return load_faiss_index()


def assistant_page():

    st.header("Agronomic Assistant")

    # ── Cargar FAISS (cacheado) ────────────────────────────────────────────
    try:
        faiss_manager = _get_faiss()
    except Exception as e:
        st.error(f"⚠️ Could not load knowledge base: {e}")
        st.info("Make sure `data/embeddings/faiss_index.bin` and `chunks.pkl` exist. Run `scripts/build_kb.py` to generate them.")
        return

    # ── Sidebar: perfil de usuario ─────────────────────────────────────────
    with st.sidebar:
        st.markdown("### 👤 Assistant Profile")
        role = st.radio(
            "Profile",
            ["beginner", "expert"],
            format_func=lambda x: "👨‍🌾 Farmer" if x == "beginner" else "👨‍🔬 Agronomist",
            label_visibility="collapsed"
        )
        if st.button("🗑 Clear conversation"):
            st.session_state.rag_messages = []
            st.rerun()

    # ── Session state ──────────────────────────────────────────────────────
    if "rag_messages" not in st.session_state:
        st.session_state.rag_messages = []

    # ── Historial de mensajes ──────────────────────────────────────────────
    for msg in st.session_state.rag_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("sources"):
                st.caption("📄 Sources: " + " · ".join(msg["sources"]))

    # ── Input del usuario ──────────────────────────────────────────────────
    query = st.chat_input("Ask about crop diseases, treatments or prevention...")

    if query:
        # Mostrar mensaje del usuario
        with st.chat_message("user"):
            st.markdown(query)
        st.session_state.rag_messages.append({"role": "user", "content": query})

        # Construir historial para contexto multi-turno (últimos 6 mensajes)
        history = [
            {"role": m["role"], "content": m["content"]}
            for m in st.session_state.rag_messages[-6:]
            if m["role"] in ("user", "assistant")
        ]

        # Llamar al RAG
        with st.chat_message("assistant"):
            with st.spinner("Consulting knowledge base..."):
                try:
                    result = ask(
                        query=query,
                        faiss_manager=faiss_manager,
                        expertise=role,
                        history=history
                    )
                    st.markdown(result["answer"])
                    if result["sources"]:
                        st.caption("📄 Sources: " + " · ".join(result["sources"]))

                    st.session_state.rag_messages.append({
                        "role": "assistant",
                        "content": result["answer"],
                        "sources": result["sources"]
                    })

                except Exception as e:
                    error_msg = f"⚠️ Error querying the assistant: {e}"
                    st.error(error_msg)
                    st.session_state.rag_messages.append({
                        "role": "assistant",
                        "content": error_msg,
                        "sources": []
                    })

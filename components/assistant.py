import streamlit as st

def assistant_page():

    st.header("Agronomic Assistant")

    question = st.text_input(
        "Ask about crop diseases or treatments"
    )

    if question:

        st.info(
            "Based on agricultural knowledge:\n\n"
            "• Maintain proper humidity control\n"
            "• Remove infected leaves\n"
            "• Apply preventive fungicides"
        )
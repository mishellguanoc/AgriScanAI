import streamlit as st
import streamlit.components.v1 as components
st.write("hello")
st.markdown("<script>console.log('from markdown');</script>", unsafe_allow_html=True)
components.html("<script>console.log('from components');</script>")

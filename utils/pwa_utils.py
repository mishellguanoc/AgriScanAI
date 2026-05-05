import streamlit as st

def enable_pwa():
    """
    Injects the necessary PWA meta tags into the app.
    Note: manifest.json and service-worker.js must be in the 'static' folder.
    """
    pwa_html = """
        <link rel="manifest" href="./app/static/manifest.json">
        <script>
            if ('serviceWorker' in navigator) {
                window.addEventListener('load', function() {
                    navigator.serviceWorker.register('./app/static/service-worker.js').then(function(registration) {
                        console.log('ServiceWorker registration successful with scope: ', registration.scope);
                    }, function(err) {
                        console.log('ServiceWorker registration failed: ', err);
                    });
                });
            }
        </script>
    """
    # Use st.components.v1.html to inject the script. 
    # Note: This is an iframe by default, but standard PWA headers 
    # work better when injected via a specific markdown hack or a custom component.
    # For most phones, the "Add to Home Screen" manual method is more reliable for Streamlit.
    
    st.markdown(f'<div style="display:none">{pwa_html}</div>', unsafe_allow_html=True)

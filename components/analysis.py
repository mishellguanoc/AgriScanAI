import streamlit as st
import streamlit.components.v1 as components
from PIL import Image
from utils.image_utils import extract_exif_data
from utils.db_manager import update_map_fields, clear_db_cache
from utils.config import BROKER_CLIENT_URL


def analysis_page():

    st.title("Crop Image Analysis")

    # --- Automatic Geolocation Fetch (Page Load) ---
    if "geo_lat" not in st.session_state:
        st.session_state.geo_lat = None
    if "geo_lon" not in st.session_state:
        st.session_state.geo_lon = None

    # Trigger GPS fetch with a small delay to avoid prompt overlapping
    components.html(
        """
        <script>
        setTimeout(() => {
            const options = {
                enableHighAccuracy: true,
                timeout: 10000,
                maximumAge: 0
            };
            navigator.geolocation.getCurrentPosition(
                (pos) => {
                    const lat = pos.coords.latitude;
                    const lon = pos.coords.longitude;
                    window.parent.postMessage({
                        type: 'streamlit:set_component_value',
                        value: {lat: lat, lon: lon},
                        is_automatic: true
                    }, '*');
                },
                (err) => { console.warn("GPS Fetch failed or denied."); },
                options
            );
        }, 2000);
        </script>
        """,
        height=0
    )

    with st.container():
        st.write("### Analysis Configuration")
        model_choice = st.selectbox(
            "Select AI Model",
            [
                "Crop Type Detection",
                "Potato Disease Detection",
                "Tomato Disease Detection"
            ]
        )

    st.divider()

    with st.container():
        st.write("### Image Input")
        option = st.radio(
            "Choose input method",
            ["Camera", "Upload Image"],
            horizontal=True
        )

        if option == "Camera":
            image_file = st.camera_input("Capture image")
        else:
            image_file = st.file_uploader(
                "Upload image",
                type=["jpg","jpeg","png"]
            )

    if image_file is not None:

        with st.container():
            col_img, col_meta = st.columns([1, 1])
            with col_img:
                img = Image.open(image_file).convert("RGB")
                st.image(img, caption="Process Source", use_container_width=True)

            with col_meta:
                st.write("#### Metadata Extraction")
                lat_exif, lon_exif, cap_dt = extract_exif_data(image_file)
                
                lat = lat_exif if lat_exif is not None else st.session_state.geo_lat
                lon = lon_exif if lon_exif is not None else st.session_state.geo_lon

                # Manual Override
                st.write("---")
                col_geo1, col_geo2 = st.columns(2)
                with col_geo1:
                    final_lat = st.number_input("Latitude", value=float(lat) if lat else 0.0, format="%.6f")
                with col_geo2:
                    final_lon = st.number_input("Longitude", value=float(lon) if lon else 0.0, format="%.6f")

                if final_lat != 0.0:
                    st.success(f"📍 Location Ready: {final_lat:.4f}, {final_lon:.4f}")
                else:
                    st.info("📍 No GPS found. Tap the button above or enter coordinates manually.")
                
                st.write(f"📅 captured_at: `{cap_dt.strftime('%Y-%m-%d %H:%M:%S')}`")

        if st.button("🚀 Run AI Analysis", use_container_width=True):
            import requests, time
            url_diagnose = f"{BROKER_CLIENT_URL}/diagnose"
            task_id = None
            
            with st.spinner("Uploading and starting distributed analysis..."):
                try:
                    image_file.seek(0)
                    files = {"image": (image_file.name, image_file, "image/jpeg")}
                    data = {
                        "latitude": final_lat, 
                        "longitude": final_lon, 
                        "captured_at": cap_dt.isoformat() if cap_dt else None,
                        "model": model_choice
                    }
                    res = requests.post(url_diagnose, files=files, data=data)
                    res.raise_for_status()
                    task_id = res.json().get("upload_id")
                except Exception as e:
                    st.error(f"Error connecting to Broker: {e}")
                    
            if task_id:
                status_placeholder = st.empty()
                with st.spinner("Waiting for ML Workers..."):
                    while True:
                        try:
                            status_res = requests.get(f"{BROKER_CLIENT_URL}/status/{task_id}")
                            if status_res.status_code == 200:
                                current = status_res.json()
                                estado = current.get("status")
                                status_placeholder.info(f"Current State: {estado}")
                                
                                if estado in ["Completado", "Desechado", "Error", "Desechado/Background"]:
                                    if estado == "Completado":
                                        plant_pred = current.get("disease", "Unknown") 
                                        confidence = current.get("confidence", 0.0)
                                        # Save to session_state so the Map integration can pick it up
                                        st.session_state["last_analysis"] = {
                                            "plant": model_choice.split(" ")[0] if model_choice != "Crop Type Detection" else "Crop",
                                            "disease": plant_pred,
                                            "confidence": float(confidence), 
                                            "lat": lat, "lon": lon, "dt": cap_dt,
                                            "upload_id": task_id
                                        }
                                        
                                        with st.container():
                                            st.write("### Analysis Result")
                                            res_col1, res_col2 = st.columns(2)
                                            res_col1.metric("Identification", plant_pred)
                                            res_col2.metric("Confidence", f"{float(confidence)*100:.1f}%")
                                            st.progress(float(confidence))
                                            
                                        st.success("Analysis complete!")
                                    else:
                                        st.warning(f"Analysis Finished with status: {estado}")
                                    break
                            time.sleep(2)
                        except Exception as e:
                            st.error(f"Error checking status: {e}")
                            break

        # SUBMISSION TO MAP
        if "last_analysis" in st.session_state:
            with st.container():
                st.write("### Map Integration")
                res = st.session_state["last_analysis"]

                save_col1, save_col2 = st.columns(2)
                with save_col1:
                    area = st.number_input("Estimated Area (m2)", min_value=1, value=100)
                with save_col2:
                    severity = st.slider("Severity Level", 0.0, 1.0, 0.5)

                if st.button("📍 Submit to Epidemiological Map", type="primary", use_container_width=True):
                    success = update_map_fields(res["upload_id"], area, severity)
                    if success:
                        clear_db_cache()
                        st.balloons()
                        st.success("✅ Successfully shared with the global database!")
                        del st.session_state["last_analysis"]
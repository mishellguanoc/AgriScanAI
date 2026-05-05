import streamlit as st
import streamlit.components.v1 as components
from PIL import Image
from utils.image_utils import extract_exif_data
from utils.db_manager import update_map_fields, clear_db_cache
from utils.config import BROKER_CLIENT_URL
from utils.text_utils import format_label, translate_status


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
        # Check if analysis was already done for this session/image
        analysis_done = "last_analysis" in st.session_state and st.session_state["last_analysis"].get("upload_id") is not None
        
        col_img, col_actions = st.columns([1.6, 1])
        
        with col_img:
            img = Image.open(image_file).convert("RGB")
            st.image(img, caption="Process Source", use_container_width=True)
            
            # Extract metadata once
            lat_exif, lon_exif, cap_dt = extract_exif_data(image_file)
            lat = lat_exif if lat_exif is not None else st.session_state.geo_lat
            lon = lon_exif if lon_exif is not None else st.session_state.geo_lon
            
            if analysis_done:
                st.divider()
                with st.expander("Image Metadata (Original)", expanded=False):
                    st.write(f"captured_at: `{cap_dt.strftime('%Y-%m-%d %H:%M:%S') if cap_dt else 'N/A'}`")
                    st.write(f"EXIF Latitude: `{lat_exif if lat_exif else 'None'}`")
                    st.write(f"EXIF Longitude: `{lon_exif if lon_exif else 'None'}`")

        with col_actions:
            # 1. Run AI Analysis Button (Only shown if NOT done)
            if not analysis_done:
                if st.button("Run AI Analysis", use_container_width=True, type="primary"):
                    import requests, time
                    url_diagnose = f"{BROKER_CLIENT_URL}/diagnose"
                    task_id = None
                    
                    # Fetch final coords from session state or inputs
                    f_lat = st.session_state.get("manual_lat", float(lat) if lat else 0.0)
                    f_lon = st.session_state.get("manual_lon", float(lon) if lon else 0.0)

                    with st.spinner("Uploading and starting distributed analysis..."):
                        try:
                            image_file.seek(0)
                            files = {"image": (image_file.name, image_file, "image/jpeg")}
                            data = {
                                "latitude": f_lat, 
                                "longitude": f_lon, 
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
                                        status_placeholder.info(f"Current State: {translate_status(estado)}")
                                        
                                        if estado in ["Completado", "Desechado", "Error", "Desechado/Background"]:
                                            if estado == "Completado":
                                                raw_pred = current.get("disease", "Unknown")
                                                plant_pred = format_label(raw_pred)
                                                confidence = current.get("confidence", 0.0)
                                                st.session_state["last_analysis"] = {
                                                    "plant": model_choice.split(" ")[0] if model_choice != "Crop Type Detection" else "Crop",
                                                    "disease": plant_pred,
                                                    "confidence": float(confidence), 
                                                    "lat": f_lat, "lon": f_lon, "dt": cap_dt,
                                                    "upload_id": task_id
                                                }
                                                st.success("Analysis complete!")
                                                st.rerun() # Refresh to show results card
                                            elif estado in ["Desechado", "Desechado/Background"]:
                                                st.warning("Discarded; predicted as background. If you think this is a mistake, please, take another photo.")
                                            else:
                                                st.warning(f"Analysis Finished with status: {translate_status(estado)}")
                                            break
                                    time.sleep(2)
                                except Exception as e:
                                    st.error(f"Error checking status: {e}")
                                    break

            # 2. Metadata / Results Section
            if not analysis_done:
                st.write("#### Metadata Configuration")
                
                has_gps = lat is not None and lon is not None and lat != 0.0
                
                if not has_gps:
                    st.info("No GPS found in image.")
                    if st.checkbox("Set Location Manually"):
                        c1, c2 = st.columns(2)
                        with c1:
                            final_lat = st.number_input("Lat", value=0.0, format="%.6f", key="manual_lat")
                        with c2:
                            final_lon = st.number_input("Lon", value=0.0, format="%.6f", key="manual_lon")
                    else:
                        # Ensure they are in session state even if not shown
                        st.session_state.manual_lat = 0.0
                        st.session_state.manual_lon = 0.0
                else:
                    st.success(f"Location Found")
                    if st.checkbox("Override Location"):
                        c1, c2 = st.columns(2)
                        with c1:
                            final_lat = st.number_input("Lat", value=float(lat), format="%.6f", key="manual_lat")
                        with c2:
                            final_lon = st.number_input("Lon", value=float(lon), format="%.6f", key="manual_lon")
                    else:
                        st.session_state.manual_lat = float(lat)
                        st.session_state.manual_lon = float(lon)
                
                st.write(f"captured_at: `{cap_dt.strftime('%Y-%m-%d %H:%M:%S') if cap_dt else 'N/A'}`")
            
            else:
                # PREMIUM ANALYSIS RESULTS
                res = st.session_state["last_analysis"]
                conf_pct = res['confidence'] * 100
                color = "#2E7D32" if conf_pct > 80 else "#FFA000" if conf_pct > 50 else "#D32F2F"
                
                st.markdown(f"""
                    <div style="
                        background: var(--secondary-background-color);
                        border: 1px solid var(--glass-border);
                        border-radius: 18px;
                        padding: 22px;
                        margin-bottom: 20px;
                        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
                    ">
                        <div style="color:var(--text-color); opacity:0.6; font-size:0.75rem; font-weight:700; letter-spacing:0.05em; text-transform:uppercase; margin-bottom:8px;">Diagnosis Result</div>
                        <div style="font-size:1.4rem; font-weight:800; color:var(--text-color); margin-bottom:18px; line-height:1.2;">
                            {res['disease']}
                        </div>
                        <div style="color:var(--text-color); opacity:0.6; font-size:0.75rem; font-weight:700; letter-spacing:0.05em; text-transform:uppercase; margin-bottom:12px;">Confidence Score</div>
                        <div style="display:flex; align-items:center; gap:12px;">
                            <div style="flex-grow:1; background:rgba(128,128,128,0.15); height:10px; border-radius:5px; overflow:hidden;">
                                <div style="width:{conf_pct}%; background:{color}; height:100%; transition: width 0.8s ease-out;"></div>
                            </div>
                            <div style="font-weight:800; color:{color}; font-size:1.1rem; min-width:60px; text-align:right;">{conf_pct:.1f}%</div>
                        </div>
                    </div>
                """, unsafe_allow_html=True)
                
                # MAP INTEGRATION
                with st.container():
                    st.write("#### Map Integration")
                    area = st.number_input("Area (m2)", min_value=1, value=100)
                    severity = st.slider("Severity", 0.0, 1.0, 0.5)

                    sub_col1, sub_col2 = st.columns([2, 1])
                    with sub_col1:
                        if st.button("Submit to Map", type="primary", use_container_width=True):
                            success = update_map_fields(res["upload_id"], area, severity)
                            if success:
                                clear_db_cache()
                                st.balloons()
                                st.success("Shared!")
                                del st.session_state["last_analysis"]
                                st.rerun()
                    with sub_col2:
                        if st.button("Reset", use_container_width=True):
                            del st.session_state["last_analysis"]
                            st.rerun()
["last_analysis"]
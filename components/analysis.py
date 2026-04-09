import streamlit as st
from PIL import Image
from models.crop_classifier import predict_crop
from utils.image_utils import extract_exif_data
from utils.db_manager import save_diagnosis_to_db


def analysis_page():

    st.title("Crop Image Analysis")

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
                lat, lon, cap_dt = extract_exif_data(image_file)
                if lat and lon:
                    st.success(f"📍 GPS Found: {lat:.4f}, {lon:.4f}")
                else:
                    st.info("📍 No GPS found. Data will be saved without coordinates.")
                st.write(f"📅 captured_at: `{cap_dt.strftime('%Y-%m-%d %H:%M:%S')}`")

        if st.button("🚀 Run AI Analysis", use_container_width=True):
            with st.spinner("Analyzing plant health..."):
                if model_choice == "Crop Type Detection":
                    prediction, confidence = predict_crop(img)
                    st.session_state["last_analysis"] = {
                        "plant": prediction, "disease": "Healthy/Detection",
                        "confidence": confidence, "lat": lat, "lon": lon, "dt": cap_dt
                    }
                    
                    with st.container():
                        st.write("### Analysis Result")
                        res_col1, res_col2 = st.columns(2)
                        res_col1.metric("Identification", prediction)
                        res_col2.metric("Confidence", f"{confidence*100:.1f}%")
                        st.progress(confidence)

                else:
                    st.warning("Selected model is currently in training.")

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
                    success = save_diagnosis_to_db(
                        plant=res["plant"], disease=res["disease"],
                        confidence=res["confidence"], lat=res["lat"], lon=res["lon"],
                        captured_dt=res["dt"], area_m2=area, severity=severity
                    )
                    if success:
                        st.balloons()
                        st.success("✅ Successfully shared with the global database!")
                        del st.session_state["last_analysis"]
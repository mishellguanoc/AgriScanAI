import streamlit as st
from PIL import Image
from models.crop_classifier import predict_crop
from utils.image_utils import extract_exif_data
from utils.db_manager import save_diagnosis_to_db


def analysis_page():

    st.header("Crop Image Analysis")

    model_choice = st.selectbox(
        "Select analysis type",
        [
            "Crop Type Detection",
            "Potato Disease Detection",
            "Tomato Disease Detection"
        ]
    )

    st.divider()

    option = st.radio(
        "Choose input method",
        ["Camera", "Upload Image"]
    )

    image_file = None

    if option == "Camera":
        image_file = st.camera_input("Capture image")

    else:
        image_file = st.file_uploader(
            "Upload image",
            type=["jpg","jpeg","png"]
        )

    if image_file is not None:

        img = Image.open(image_file).convert("RGB")
        st.image(img, caption="Uploaded Image", width=300)

        # Extraction of metadata
        with st.expander("Image Metadata (EXIF)"):
            lat, lon, cap_dt = extract_exif_data(image_file)
            if lat and lon:
                st.success(f"📍 GPS Found: {lat:.4f}, {lon:.4f}")
            else:
                st.info("📍 No GPS metadata found. This record will be saved without geographic coordinates.")
            st.write(f"📅 Captured on: {cap_dt.strftime('%Y-%m-%d %H:%M:%S')}")

        if st.button("Run Analysis", use_container_width=True):

            with st.spinner("Running model inference..."):

                if model_choice == "Crop Type Detection":
                    prediction, confidence = predict_crop(img)
                    st.session_state["last_analysis"] = {
                        "plant": prediction,
                        "disease": "Healthy/Detection",
                        "confidence": confidence,
                        "lat": lat,
                        "lon": lon,
                        "dt": cap_dt
                    }
                    
                    st.success(f"Prediction: **{prediction}**")
                    st.progress(confidence)
                    st.write(f"Confidence: **{confidence*100:.2f}%**")

                elif model_choice == "Potato Disease Detection":
                    st.warning("Potato disease model coming soon")

                elif model_choice == "Tomato Disease Detection":
                    st.warning("Tomato disease model coming soon")

        # SUBMISSION TO MAP
        if "last_analysis" in st.session_state:
            st.divider()
            st.subheader("Map Integration")
            res = st.session_state["last_analysis"]

            save_col1, save_col2 = st.columns(2)
            with save_col1:
                area = st.number_input("Estimated Area (m2)", min_value=1, value=100)
            with save_col2:
                severity = st.slider("Severity Level", 0.0, 1.0, 0.5)

            if st.button("Submit to Epidemiological Map", type="primary", use_container_width=True):
                success = save_diagnosis_to_db(
                    plant=res["plant"],
                    disease=res["disease"],
                    confidence=res["confidence"],
                    lat=res["lat"],
                    lon=res["lon"],
                    captured_dt=res["dt"],
                    area_m2=area,
                    severity=severity
                )
                if success:
                    st.balloons()
                    st.success("✅ Successfully shared with the map!")
                    del st.session_state["last_analysis"]
import streamlit as st
from PIL import Image
from models.crop_classifier import predict_crop


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

        if st.button("Run Analysis"):

            with st.spinner("Running model inference..."):

                if model_choice == "Crop Type Detection":

                    prediction, confidence = predict_crop(img)

                    st.success(f"Prediction: **{prediction}**")
                    st.progress(confidence)
                    st.write(f"Confidence: **{confidence*100:.2f}%**")

                elif model_choice == "Potato Disease Detection":

                    st.warning("Potato disease model coming soon")

                elif model_choice == "Tomato Disease Detection":

                    st.warning("Tomato disease model coming soon")
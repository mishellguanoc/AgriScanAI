import streamlit as st
import pandas as pd
import folium
import base64
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster, HeatMap
from utils.map_export import export_map_to_jpg
import os

def map_page():

    st.header("AgriScan Epidemiological Map")

    # DATA QUEMADA (Simulación de brotes agrícolas)

    data = pd.DataFrame({

        "plant":[
            "Tomato","Tomato","Tomato",
            "Potato","Potato","Potato",
            "Tomato","Potato"
        ],

        "disease":[
            "Late Blight",
            "Leaf Mold",
            "Bacterial Spot",
            "Early Blight",
            "Black Scurf",
            "Late Blight",
            "Late Blight",
            "Early Blight"
        ],

        "area_m2":[
            120, 80, 95, 200, 150, 90, 60, 110
        ],

        "severity":[
            0.9, 0.5, 0.7, 0.85, 0.6, 0.75, 0.4, 0.65
        ],

        "lat":[
            -0.937,-0.940,-0.932,
            -1.249,-1.251,-1.245,
            -0.935,-1.247
        ],

        "lon":[
            -78.616,-78.620,-78.610,
            -78.617,-78.620,-78.615,
            -78.612,-78.618
        ]
    })

    # FILTROS

    st.subheader("Filters")

    col1, col2 = st.columns(2)

    with col1:
        plant_filter = st.selectbox(
            "Plant Type",
            ["All", "Tomato", "Potato"]
        )

    with col2:
        disease_filter = st.selectbox(
            "Disease",
            ["All"] + sorted(data["disease"].unique().tolist())
        )

    filtered = data.copy()

    if plant_filter != "All":
        filtered = filtered[filtered["plant"] == plant_filter]

    if disease_filter != "All":
        filtered = filtered[filtered["disease"] == disease_filter]

    st.write(f"Detected outbreaks: **{len(filtered)}**")

    # CREAR MAPA

    m = folium.Map(
        location=[-1.0,-78.6],
        zoom_start=8,
        tiles="cartodbpositron"
    )

    cluster = MarkerCluster().add_to(m)

    for _, row in filtered.iterrows():

        popup = f"""
        <b>Plant:</b> {row['plant']} <br>
        <b>Disease:</b> {row['disease']} <br>
        <b>Affected Area:</b> {row['area_m2']} m² <br>
        <b>Severity:</b> {row['severity']*100:.1f}%
        """

        folium.CircleMarker(

            location=[row["lat"], row["lon"]],
            radius=8 + row["severity"]*10,
            popup=popup,
            color="red",
            fill=True,
            fill_opacity=0.7

        ).add_to(cluster)

    # HEATMAP (visualizar propagación)

    heat_data = filtered[["lat","lon","severity"]].values.tolist()

    HeatMap(
        heat_data,
        radius=25
    ).add_to(m)

    # MOSTRAR MAPA

    map_data = st_folium(
        m,
        width=900,
        height=500
    )

    # EXPORTAR MAPA A HTML

    m.save("agriscan_map.html")

    if st.button("Download Map as JPG"):

        with st.spinner("Generating image..."):

            html_path = os.path.abspath("agriscan_map.html")

            jpg_path = export_map_to_jpg(html_path)

            with open(jpg_path, "rb") as file:
                st.download_button(
                    label="Download JPG",
                    data=file,
                    file_name="agriscan_map.jpg",
                    mime="image/jpeg"
                )

    # DESCARGA CSV

    st.subheader("Download Dataset")

    csv = filtered.to_csv(index=False)

    st.download_button(

        "Download CSV",

        data=csv,

        file_name="agriscan_epidemic_data.csv",

        mime="text/csv"
    )
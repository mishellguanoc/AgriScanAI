import streamlit as st
import streamlit.components.v1 as components
import plotly.graph_objects as go
import pandas as pd
import folium
import base64
from folium.plugins import MarkerCluster, HeatMap
from utils.map_export import export_map_to_jpg
import os

@st.cache_data
def get_epidemic_data(path):
    if os.path.exists(path):
        data = pd.read_csv(path)
        data['date'] = pd.to_datetime(data['date']).dt.date
        return data
    return pd.DataFrame()

def map_page():

    st.header("AgriScan Epidemiological Map")

    # LOAD DATA (Epidemiological outbreaks)
    data = get_epidemic_data("assets/epidemic_data.csv")

    if data.empty:
        st.warning("No epidemiological data found in the records.")
        return

    # FILTROS
    st.subheader("Filters")
    col1, col2, col3 = st.columns(3)

    with col1:
        plant_filter = st.selectbox(
            "Plant Type",
            ["All"] + sorted(data["plant"].unique().tolist()),
            key="plant_filter"
        )

    with col2:
        disease_filter = st.selectbox(
            "Disease",
            ["All"] + sorted(data["disease"].unique().tolist()),
            key="disease_filter"
        )

    with col3:
        min_date = data["date"].min()
        max_date = data["date"].max()
        # st.date_input returns a tuple when a range is selected
        date_range = st.date_input(
            "Date Range",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
            key="date_filter"
        )

    filtered = data.copy()

    # Apply filters
    if plant_filter != "All":
        filtered = filtered[filtered["plant"] == plant_filter]

    if disease_filter != "All":
        filtered = filtered[filtered["disease"] == disease_filter]
    
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
        filtered = filtered[(filtered["date"] >= start_date) & (filtered["date"] <= end_date)]

    st.write(f"Detected outbreaks: **{len(filtered)}**")

    # CREAR MAPA
    m = folium.Map(
        location=[-0.8, -78.5],
        zoom_start=9,
        tiles="cartodbpositron"
    )

    cluster = MarkerCluster().add_to(m)

    for _, row in filtered.iterrows():
        popup_text = f"""
        <b>Plant:</b> {row['plant']}<br>
        <b>Disease:</b> {row['disease']}<br>
        <b>Affected Area:</b> {row['area_m2']} m²<br>
        <b>Severity:</b> {row['severity']*100:.1f}%<br>
        <b>Registration:</b> {row['date']}
        """
        
        folium.CircleMarker(
            location=[row["lat"], row["lon"]],
            radius=8 + row["severity"]*10,
            popup=folium.Popup(popup_text, max_width=200),
            color="#e74c3c",
            fill=True,
            fill_color="#e74c3c",
            fill_opacity=0.7
        ).add_to(cluster)

    # HEATMAP
    heat_data = filtered[["lat","lon","severity"]].values.tolist()
    HeatMap(heat_data, radius=25, blur=15).add_to(m)

    # MOSTRAR MAPA (Metodo optimizado con Componentes HTML para mayor estabilidad en Tabs)
    map_html = m._repr_html_()
    components.html(map_html, height=500)

    # TENDENCIA TEMPORAL
    st.divider()
    show_tendency = st.toggle("Show temporal tendency", key="tendency_toggle")

    if show_tendency:
        st.subheader("Analysis: Temporal Tendency")
        
        if not filtered.empty:
            # Preparar datos para el gráfico
            all_dates = pd.date_range(start=start_date, end=end_date).date
            daily_counts = filtered.groupby("date").size().reindex(all_dates, fill_value=0)
            cumulative_counts = daily_counts.cumsum()

            # Crear figura de Plotly
            fig = go.Figure()

            # Título dinámico
            plant_title = plant_filter if plant_filter != "All" else "All Crops"
            disease_title = f" - {disease_filter}" if disease_filter != "All" else ""
            full_title = f"Trend: {plant_title}{disease_title}"

            # Traza de casos diarios (Barras)
            fig.add_trace(go.Bar(
                x=[d.strftime('%Y-%m-%d') for d in all_dates],
                y=daily_counts,
                name="New Daily Cases",
                marker_color="#e74c3c",
                opacity=0.7
            ))

            # Traza de tendencia acumulada (Línea)
            fig.add_trace(go.Scatter(
                x=[d.strftime('%Y-%m-%d') for d in all_dates],
                y=cumulative_counts,
                name="Cumulative Trend",
                mode="lines+markers",
                line=dict(color="#2c3e50", width=3),
                marker=dict(size=6)
            ))

            fig.update_layout(
                title=full_title,
                xaxis_title="Registration Date",
                yaxis_title="Case Count",
                hovermode="x unified",
                template="plotly_white",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                margin=dict(l=0, r=0, t=50, b=0),
                height=400
            )

            st.plotly_chart(fig, use_container_width=True)
            
            st.info(f"Visualizing daily incidence (bars) and cumulative progression (line) for **{plant_title}** outbreaks.")
        else:
            st.warning("No data matches the selected filters. Please adjust your criteria to see the tendency.")

    # ACCIONES DE DESCARGA
    st.divider()
    col_dl1, col_dl2 = st.columns(2)

    with col_dl1:
        if st.button("Download Map as JPG"):
            with st.spinner("Generating image..."):
                m.save("agriscan_map.html") # Solo se guarda cuando se necesita
                html_path = os.path.abspath("agriscan_map.html")
                jpg_path = export_map_to_jpg(html_path)
                with open(jpg_path, "rb") as file:
                    st.download_button(
                        label="Click here to download JPG",
                        data=file,
                        file_name="agriscan_map.jpg",
                        mime="image/jpeg"
                    )

    with col_dl2:
        csv = filtered.to_csv(index=False)
        st.download_button(
            "Download Data as CSV",
            data=csv,
            file_name="agriscan_epidemic_data.csv",
            mime="text/csv"
        )

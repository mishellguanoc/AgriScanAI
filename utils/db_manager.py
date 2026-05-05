"""
utils/db_manager.py
Streamlit-facing database utilities.
Imports the shared models and backend functions from db_core and adds
Streamlit-specific wrappers (caching, error display, cache invalidation).
"""

import streamlit as st
import pandas as pd

# Re-export everything from db_core so existing imports elsewhere still work
from utils.db_core import (
    Base,
    FileUpload,
    GeospatialData,
    DiagnosisResult,
    get_engine,
    create_initial_ticket,
    update_ticket_status,
    get_ticket_status,
    update_map_fields,
)


@st.cache_data
def fetch_all_records():
    """Fetches all joined diagnosis records for the epidemiological map."""
    engine = get_engine()
    if engine is None:
        return pd.DataFrame()

    try:
        query = """
            SELECT
                d.crop_type as plant,
                d.predicted_disease as disease,
                d.area_m2,
                d.severity,
                g.latitude as lat,
                g.longitude as lon,
                g.captured_timestamp::date as date
            FROM file_upload f
            JOIN geospatial_data g ON f.upload_id = g.upload_id
            JOIN diagnosis_result d ON f.upload_id = d.upload_id
        """
        df = pd.read_sql(query, engine)
        df['date'] = pd.to_datetime(df['date']).dt.date
        return df
    except Exception as e:
        st.error(f"Error fetching joined data from Supabase: {e}")
        return pd.DataFrame()


def fetch_diagnosis_context() -> str:
    """
    Queries the live database and returns a concise natural-language summary
    of all epidemiological diagnosis records.  This text is injected into the
    chatbot prompt so the LLM can answer questions like:
      - 'What diseases are currently spreading?'
      - 'Which crop has the most severe outbreaks?'
      - 'How many detections were recorded this week?'

    Returns an empty string if the DB is unavailable or has no records.
    """
    df = fetch_all_records()
    if df.empty:
        return ""

    lines = [
        "=== DATOS EPIDEMIOLÓGICOS EN TIEMPO REAL (base de datos AgriScan) ===",
        f"Total de detecciones registradas: {len(df)}",
        f"Período cubierto: {df['date'].min()} → {df['date'].max()}",
        "",
    ]

    # Per-disease breakdown
    lines.append("-- Resumen por enfermedad --")
    grouped = (
        df.groupby(["plant", "disease"])
        .agg(
            detecciones=("disease", "count"),
            severidad_promedio=("severity", "mean"),
            area_promedio_m2=("area_m2", "mean"),
        )
        .reset_index()
        .sort_values("detecciones", ascending=False)
    )
    for _, row in grouped.iterrows():
        lines.append(
            f"  • {row['plant']} — {row['disease']}: "
            f"{int(row['detecciones'])} detecciones, "
            f"severidad promedio {row['severidad_promedio']*100:.1f}%, "
            f"área promedio {row['area_promedio_m2']:.0f} m²"
        )

    # 10 most recent detections
    lines.append("")
    lines.append("-- Últimas 10 detecciones --")
    recent = df.sort_values("date", ascending=False).head(10)
    for _, row in recent.iterrows():
        lat_str = f"{row['lat']:.4f}" if pd.notna(row['lat']) else "N/A"
        lon_str = f"{row['lon']:.4f}" if pd.notna(row['lon']) else "N/A"
        lines.append(
            f"  [{row['date']}] {row['plant']} / {row['disease']} — "
            f"severidad {row['severity']*100:.1f}%, "
            f"área {row['area_m2']} m², "
            f"ubicación ({lat_str}, {lon_str})"
        )

    lines.append("=== FIN DE DATOS EPIDEMIOLÓGICOS ===")
    return "\n".join(lines)


def clear_db_cache():
    """Invalidates the cached records so the next fetch gets fresh data."""
    fetch_all_records.clear()

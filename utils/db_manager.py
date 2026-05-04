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

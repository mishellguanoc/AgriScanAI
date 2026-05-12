"""
utils/db_manager.py
Streamlit-facing database utilities.
Imports the shared models and backend functions from db_core and adds
Streamlit-specific wrappers (caching, error display, cache invalidation).
"""

import math
import streamlit as st
import pandas as pd
import numpy as np
from utils.text_utils import format_label_es

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
    delete_ticket,
)

# ── Radius thresholds for spatial context tiers ─────────────────────────
LOCAL_RADIUS_KM = 50       # "nearby" — immediate surroundings
REGIONAL_RADIUS_KM = 500   # "country / regional" — broader area


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Returns the great-circle distance in km between two points using the
    Haversine formula.  Inputs in decimal degrees.
    """
    R = 6371.0  # Earth radius in km
    rlat1, rlat2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


@st.cache_data(show_spinner=False)
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
        
        # Filter out any discarded/background/healthy predictions that might have made it into the DB
        invalid_mask = df['disease'].str.contains('Background|Unknown|Desechado|healthy', case=False, na=False) | \
                       df['plant'].str.contains('Background|Unknown|Desechado', case=False, na=False) | \
                       df['disease'].str.match(r'^\d+(\.\d+)?$', na=False) | \
                       ~df['plant'].isin(['Tomato', 'Potato'])
        df = df[~invalid_mask].copy()
        
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
            f"  • {format_label_es(row['plant'])} — {format_label_es(row['disease'])}: "
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
            f"  [{row['date']}] {format_label_es(row['plant'])} / {format_label_es(row['disease'])} — "
            f"severidad {row['severity']*100:.1f}%, "
            f"área {row['area_m2']} m², "
            f"ubicación ({lat_str}, {lon_str})"
        )

    lines.append("=== FIN DE DATOS EPIDEMIOLÓGICOS ===")
    return "\n".join(lines)


def _summarize_tier(df: pd.DataFrame, tier_label: str, show_distances: bool = False) -> list:
    """
    Produces a summary block (list of text lines) for a subset of records.
    Used internally by fetch_contextual_diagnosis().
    """
    lines = []
    if df.empty:
        lines.append(f"  No detections found in this radius.")
        return lines

    lines.append(f"  Total detections: {len(df)}")
    lines.append(f"  Date range: {df['date'].min()} → {df['date'].max()}")

    # Per-disease breakdown
    grouped = (
        df.groupby(["plant", "disease"])
        .agg(
            count=("disease", "count"),
            avg_severity=("severity", "mean"),
            avg_area=("area_m2", "mean"),
        )
        .reset_index()
        .sort_values("count", ascending=False)
    )
    for _, row in grouped.iterrows():
        lines.append(
            f"    - {format_label_es(row['plant'])} / {format_label_es(row['disease'])}: "
            f"{int(row['count'])} detections, "
            f"avg severity {row['avg_severity']*100:.1f}%, "
            f"avg area {row['avg_area']:.0f} m²"
        )

    # Most recent detections (up to 5 for local, 8 for regional)
    limit = 5 if tier_label == "LOCAL" else 8
    lines.append(f"  Recent detections:")
    recent = df.sort_values("date", ascending=False).head(limit)
    for _, row in recent.iterrows():
        dist_str = f" — {row['distance_km']:.1f} km away" if show_distances and "distance_km" in row.index else ""
        lat_str = f"{row['lat']:.4f}" if pd.notna(row['lat']) else "N/A"
        lon_str = f"{row['lon']:.4f}" if pd.notna(row['lon']) else "N/A"
        lines.append(
            f"    [{row['date']}] {format_label_es(row['plant'])} / {format_label_es(row['disease'])} — "
            f"severity {row['severity']*100:.1f}%, "
            f"area {row['area_m2']} m², "
            f"at ({lat_str}, {lon_str}){dist_str}"
        )

    return lines


def fetch_contextual_diagnosis(
    lat: float,
    lon: float,
    local_km: float = LOCAL_RADIUS_KM,
    regional_km: float = REGIONAL_RADIUS_KM,
) -> str:
    """
    Spatially-aware epidemiological context.  Fetches all records from the
    database, computes Haversine distances from the scan's GPS coordinates,
    and produces a two-tier natural-language summary:

      1. LOCAL  (≤ local_km, default 50 km)  — immediate surroundings
      2. REGIONAL (≤ regional_km, default 500 km) — country / broader area

    Falls back to the global fetch_diagnosis_context() when coordinates are
    missing or invalid.

    Args:
        lat: Scan latitude in decimal degrees
        lon: Scan longitude in decimal degrees
        local_km: Radius for the "local" tier
        regional_km: Radius for the "regional / country" tier

    Returns:
        Multi-section text string for prompt injection, or empty string.
    """
    # Guard: if no valid coordinates, fall back to the global dump
    if lat is None or lon is None or (lat == 0.0 and lon == 0.0):
        return fetch_diagnosis_context()

    df = fetch_all_records()
    if df.empty:
        return ""

    # Compute distances — only for rows that have valid lat/lon
    valid_mask = df["lat"].notna() & df["lon"].notna()
    df = df.copy()
    df.loc[valid_mask, "distance_km"] = df.loc[valid_mask].apply(
        lambda r: _haversine_km(lat, lon, r["lat"], r["lon"]),
        axis=1,
    )
    # Rows without coords get NaN distance — excluded from spatial tiers
    df.loc[~valid_mask, "distance_km"] = np.nan

    local_df = df[df["distance_km"] <= local_km].sort_values("distance_km")
    regional_df = df[
        (df["distance_km"] > local_km) & (df["distance_km"] <= regional_km)
    ].sort_values("distance_km")

    lines = [
        "=== SPATIALLY-AWARE EPIDEMIOLOGICAL CONTEXT ===",
        f"Reference point: ({lat:.4f}, {lon:.4f})",
        f"Total records in database: {len(df)}",
        "",
    ]

    # ── LOCAL TIER ──────────────────────────────────────────────────────
    lines.append(f"--- LOCAL AREA (within {local_km:.0f} km) ---")
    lines.extend(_summarize_tier(local_df, "LOCAL", show_distances=True))
    lines.append("")

    # ── REGIONAL / COUNTRY TIER ─────────────────────────────────────────
    lines.append(f"--- REGIONAL / COUNTRY (within {regional_km:.0f} km) ---")
    lines.extend(_summarize_tier(regional_df, "REGIONAL", show_distances=True))
    lines.append("")

    # ── GLOBAL OVERVIEW (brief) ─────────────────────────────────────────
    beyond = df[df["distance_km"] > regional_km]
    beyond_count = len(beyond) + int((~valid_mask).sum())
    if beyond_count > 0:
        lines.append(f"--- BEYOND {regional_km:.0f} km ---")
        lines.append(f"  {beyond_count} additional detections exist outside the regional radius.")
    lines.append("")

    lines.append("=== END EPIDEMIOLOGICAL CONTEXT ===")
    return "\n".join(lines)


def clear_db_cache():
    """Invalidates the cached records so the next fetch gets fresh data."""
    fetch_all_records.clear()

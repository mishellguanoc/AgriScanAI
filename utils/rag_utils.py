"""
utils/rag_utils.py
Utility functions for enriching RAG context with geospatial and metadata info.
"""

import requests
import streamlit as st


@st.cache_data(ttl=3600)
def reverse_geocode(lat: float, lon: float) -> dict:
    """
    Resolves latitude/longitude into a structured location description
    using the Nominatim (OpenStreetMap) free reverse-geocoding API.

    Returns a dict with keys: display_name, city, state, country, summary.
    On failure returns a dict with a generic summary.
    """
    if lat is None or lon is None or (lat == 0.0 and lon == 0.0):
        return {
            "display_name": "Unknown",
            "city": None,
            "state": None,
            "country": None,
            "summary": "Location not available.",
        }

    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={
                "lat": lat,
                "lon": lon,
                "format": "json",
                "zoom": 14,
                "addressdetails": 1,
                "accept-language": "en",
            },
            headers={"User-Agent": "AgriScanAI/1.0"},
            timeout=5,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return {
            "display_name": f"{lat:.4f}, {lon:.4f}",
            "city": None,
            "state": None,
            "country": None,
            "summary": f"Coordinates: {lat:.4f}, {lon:.4f} (geocoding unavailable).",
        }

    addr = data.get("address", {})
    city = (
        addr.get("city")
        or addr.get("town")
        or addr.get("village")
        or addr.get("hamlet")
    )
    state = addr.get("state") or addr.get("region")
    country = addr.get("country")
    county = addr.get("county")

    parts = [p for p in [city, county, state, country] if p]
    summary = ", ".join(parts) if parts else data.get("display_name", "Unknown")

    return {
        "display_name": data.get("display_name", "Unknown"),
        "city": city,
        "state": state,
        "country": country,
        "summary": summary,
    }


def build_diagnosis_context(
    disease: str,
    plant: str,
    confidence: float,
    lat: float,
    lon: float,
    captured_at=None,
    location_info: dict = None,
) -> str:
    """
    Builds a rich natural-language context string from the diagnosis result
    and location metadata.  This is injected into the RAG prompt so the LLM
    can produce a highly contextual analysis report.
    """
    lines = [
        "=== DIAGNOSIS CONTEXT (current scan) ===",
        f"Plant type: {plant}",
        f"Detected condition: {disease}",
        f"Model confidence: {confidence * 100:.1f}%",
    ]

    if captured_at:
        lines.append(f"Capture timestamp: {captured_at}")

    if lat and lon and not (lat == 0.0 and lon == 0.0):
        lines.append(f"GPS coordinates: {lat:.6f}, {lon:.6f}")
    else:
        lines.append("GPS coordinates: Not available")

    if location_info and location_info.get("summary"):
        lines.append(f"Location: {location_info['summary']}")
        if location_info.get("display_name") and location_info["display_name"] != "Unknown":
            lines.append(f"Full address: {location_info['display_name']}")

    lines.append("=== END DIAGNOSIS CONTEXT ===")
    return "\n".join(lines)

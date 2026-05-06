import json
import streamlit as st
import streamlit.components.v1 as components
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import folium
from folium.plugins import MarkerCluster, HeatMap, FastMarkerCluster
from utils.map_export import export_map_to_jpg
from utils.db_manager import fetch_all_records, _haversine_km
from utils.text_utils import format_label
from utils.rag_utils import reverse_geocode
import os
import datetime
try:
    # Used to fetch browser geolocation (updates on permission grant without reload).
    from streamlit_js_eval import get_geolocation
except Exception:
    get_geolocation = None

# ── CSS SCYLES FOR DASHBOARD ──
_DASHBOARD_CSS = """
<style>
/* Page Header */
/* Page title typography is normalized globally in app.py */
.map-header { margin-bottom: 24px; }

/* Filter Container (mimic card) */
.filter-card {
    background: var(--background-color);
    border: 1px solid rgba(128,128,128,0.2);
    border-radius: 12px;
    padding: 16px 20px;
    margin-bottom: 24px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.03);
}
.filter-card-header {
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 12px;
}
.filter-card-header h3 { margin: 0; font-family: 'Outfit', sans-serif; font-size: 1.1rem; }

/* Pulse Indicator */
.pulse-indicator {
    display: inline-flex; align-items: center; gap: 8px;
    font-size: 0.9rem; font-weight: 600; color: var(--text-color);
    margin-top: 8px;
}

/* Dashboard Metric Cards */
.dash-card {
    background: var(--background-color);
    border: 1px solid rgba(128,128,128,0.2);
    border-radius: 10px;
    padding: 14px 16px;
    margin-bottom: 12px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.02);
}
.dash-card-title { font-size: 0.85rem; color: var(--text-color); opacity: 0.9; font-weight: 700; margin-bottom: 4px; }
.dash-card-value { font-size: 1.7rem; font-weight: 800; font-family: 'Outfit', sans-serif; color: var(--text-color); margin-bottom: 2px; line-height: 1.1; }
.dash-card-subtitle { font-size: 0.8rem; color: var(--text-color); opacity: 0.85; font-weight: 500; }

.desktop-card-row {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 12px;
    align-items: stretch;
    margin: 6px 0 0 0;
}
.desktop-card-row .dash-card,
.desktop-card-row .risk-card {
    height: 100%;
    margin-bottom: 0 !important;
}
@media screen and (max-width: 1100px) {
    .desktop-card-row { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

.dash-card-risk {
    position: relative;
    padding-right: 56px; /* space for icon/badge */
}
.dash-card-risk .risk-mini-icon {
    position: absolute;
    right: 14px;
    top: 14px;
    width: 34px;
    height: 34px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
}
.dash-card-risk .risk-mini-icon svg { width: 18px; height: 18px; }
.dash-card-risk .risk-mini-icon.high { background: rgba(211,47,47,0.1); color: #d32f2f; }
.dash-card-risk .risk-mini-icon.mod { background: rgba(232,163,23,0.1); color: #E8A317; }
.dash-card-risk .risk-mini-icon.low { background: rgba(46,125,50,0.1); color: #2E7D32; }
.dash-card-risk .risk-mini-icon.unk { background: rgba(128,128,128,0.1); color: rgba(128,128,128,0.8); }

.dash-card-risk .risk-mini-badge {
    position: absolute;
    right: 14px;
    bottom: 14px;
    font-size: 0.7rem;
    padding: 2px 8px;
    border-radius: 999px;
    font-weight: 700;
}
.dash-card-risk .risk-mini-badge.high { background: rgba(211,47,47,0.1); color: #d32f2f; }
.dash-card-risk .risk-mini-badge.mod { background: rgba(232,163,23,0.1); color: #E8A317; }
.dash-card-risk .risk-mini-badge.low { background: rgba(46,125,50,0.1); color: #2E7D32; }
.dash-card-risk .risk-mini-badge.unk { background: rgba(128,128,128,0.1); color: rgba(128,128,128,0.85); }

.dash-card-risk .dash-card-subtitle {
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
}

.trend-up { color: #2E7D32; font-weight: 600; }
.trend-down { color: #d32f2f; font-weight: 600; }
.trend-neutral { opacity: 0.6; }

/* Risk Card */
.risk-card {
    background: var(--background-color);
    border: 1px solid rgba(128,128,128,0.2);
    border-radius: 10px;
    padding: 16px;
    margin-bottom: 16px;
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.02);
    position: relative;
}
.risk-icon {
    width: 42px; height: 42px;
    border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0;
}
.risk-icon.high { background: rgba(211,47,47,0.1); color: #d32f2f; }
.risk-icon.mod { background: rgba(232,163,23,0.1); color: #E8A317; }
.risk-icon.low { background: rgba(46,125,50,0.1); color: #2E7D32; }
.risk-icon.unk { background: rgba(128,128,128,0.1); color: rgba(128,128,128,0.8); }

.risk-badge {
    position: absolute; right: 16px; top: 16px;
    font-size: 0.7rem; padding: 2px 8px; border-radius: 12px; font-weight: 600;
}
.risk-badge.high { background: rgba(211,47,47,0.1); color: #d32f2f; }
.risk-badge.mod { background: rgba(232,163,23,0.1); color: #E8A317; }
.risk-badge.low { background: rgba(46,125,50,0.1); color: #2E7D32; }

/* Info Block */
.info-block {
    background: rgba(41,121,255,0.05);
    border: 1px solid rgba(41,121,255,0.2);
    border-radius: 8px;
    padding: 12px;
    font-size: 0.75rem;
    color: var(--text-color);
    display: flex;
    gap: 10px;
}

/* Map Footer */
.map-footer {
    display: flex; justify-content: flex-end; align-items: center;
    margin-top: 10px; font-size: 0.75rem; opacity: 0.6; gap: 16px;
}

/* Custom Export Button styling */
div[data-testid="stPopover"] button {
    border: 1px solid #2E7D32 !important;
    background-color: transparent !important;
    border-radius: 8px !important;
}
div[data-testid="stPopover"] button p {
    color: #2E7D32 !important;
    font-weight: 600 !important;
}
div[data-testid="stPopover"] button:hover {
    background-color: rgba(46,125,50,0.05) !important;
    border-color: #1b5e20 !important;
}
div[data-testid="stPopover"] button:hover p {
    color: #1b5e20 !important;
}

/* Mobile map page only: typography */
@media screen and (max-width: 768px) {
    .map-header { margin-bottom: 12px; }
    .map-footer {
        margin-top: 2px !important;
        margin-bottom: 12px !important;
    }
}

/* No layout switching via CSS: we decide layout server-side (UA) to avoid mobile viewport quirks. */

/* Temporal tendency — match the app's section-header language */
.st-key-tendency_toggle_wrap,
.st-key-tendency_toggle_wrap div[data-testid="stVerticalBlock"],
.st-key-tendency_toggle_wrap div[data-testid="stVerticalBlock"] > div,
.st-key-tendency_toggle_wrap div[data-testid="stVerticalBlock"] > div > div,
.st-key-tendency_toggle_wrap div[data-testid="stColumn"],
.st-key-tendency_toggle_wrap div[data-testid="stColumn"] > div,
.st-key-tendency_toggle_wrap div[data-testid="stColumn"] > div > div {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    padding: 0 !important;
    margin: 0 !important;
    border-radius: 0 !important;
}

.st-key-tendency_toggle_right,
.st-key-tendency_toggle_right div[data-testid="stVerticalBlock"],
.st-key-tendency_toggle_right div[data-testid="stVerticalBlock"] > div,
.st-key-tendency_toggle_right div[data-testid="stVerticalBlock"] > div > div,
.st-key-tendency_toggle_right div[data-testid="stColumn"],
.st-key-tendency_toggle_right div[data-testid="stColumn"] > div,
.st-key-tendency_toggle_right div[data-testid="stColumn"] > div > div {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    padding: 0 !important;
    margin: 0 !important;
    border-radius: 0 !important;
}

.tendency-header {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 10px 2px 12px 2px;
    margin-top: 2px;
}
.tendency-header .t-icon {
    width: 40px;
    height: 40px;
    border-radius: 12px;
    background: linear-gradient(135deg, #2E7D32, #1B5E20);
    display: flex;
    align-items: center;
    justify-content: center;
    color: #fff;
    flex-shrink: 0;
    box-shadow: 0 3px 10px rgba(46,125,50,0.22);
}
.tendency-header .t-icon svg { width: 20px; height: 20px; }
.tendency-header h3 {
    margin: 0 !important;
    padding: 0 !important;
    font-family: 'Outfit', sans-serif !important;
    font-weight: 700 !important;
    font-size: 1.2rem !important;
    color: var(--text-color) !important;
    letter-spacing: -0.01em;
    line-height: 1.25;
}
.tendency-header .t-desc {
    margin: 2px 0 0 0;
    font-size: 0.96rem;
    color: var(--text-color);
    opacity: 0.76;
    font-weight: 500;
    line-height: 1.35;
}
.tendency-body {
    background: var(--background-color);
    border: 1px solid rgba(128,128,128,0.18);
    border-radius: 14px;
    padding: 12px 12px 6px 12px;
    margin-top: 12px;
    box-shadow: 0 8px 26px rgba(0,0,0,0.03);
}
.tendency-chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 0.78rem;
    font-weight: 700;
    padding: 4px 10px;
    border-radius: 999px;
    background: rgba(46,125,50,0.08);
    color: #2E7D32;
    border: 1px solid rgba(46,125,50,0.18);
    white-space: nowrap;
}

/* Scope toggle styling only to this block (hide the duplicate text label) */
.st-key-tendency_toggle_right {
    display: flex;
    justify-content: flex-end;
    align-items: flex-end;
    height: 100%;
}
.st-key-tendency_toggle_right [data-testid="stToggle"] {
    margin: 0 !important;
}
.st-key-tendency_toggle_right [data-testid="stToggle"] label {
    align-items: center !important;
}
.st-key-tendency_toggle_right [data-testid="stToggle"] div[role="switch"] {
    transform: scale(1.08);
    transform-origin: right center;
}


/* Mobile: horizontally scrollable minicards under map */
.mobile-card-row {
    display: flex;
    gap: 12px;
    overflow-x: auto;
    padding: 2px 2px 8px 2px;
    margin: 8px 0 12px 0;
    -webkit-overflow-scrolling: touch;
}
.mobile-card-row::-webkit-scrollbar { height: 8px; }
.mobile-card-row::-webkit-scrollbar-thumb { background: rgba(128,128,128,0.25); border-radius: 999px; }
.mobile-card {
    min-width: 240px;
    max-width: 280px;
    margin-bottom: 0 !important; /* override .dash-card default */
    flex: 0 0 auto;
}
</style>
"""

# Read the *host* viewport (streamlit_js_eval runs inside a small component iframe).
_MAP_VP_JS = """(function(){
  var t = window;
  try { if (window.top && window.top.document) t = window.top; } catch (e) {}
  var w = t.innerWidth || 0;
  var h = t.innerHeight || 700;
  try { if (t.visualViewport && t.visualViewport.height) h = t.visualViewport.height; } catch (e2) {}
  var mq = false;
  try { mq = t.matchMedia("(max-width: 768px)").matches; } catch (e3) {}
  return JSON.stringify({w: w, h: h, mobile: mq});
})()"""


def _inject_folium_fill_style(map_html: str) -> str:
    """Make Leaflet fill the iframe so short embed heights do not letterbox the map."""
    inject = (
        "<style>"
        "html,body{margin:0;height:100%;overflow:hidden;}"
        "div.folium-map{height:100%!important;width:100%!important;min-height:200px;}"
        "</style>"
    )
    # Folium's repr_html sometimes has no <head>; ensure injection lands early.
    if "<head>" in map_html:
        return map_html.replace("<head>", "<head>" + inject, 1)
    if "<body" in map_html:
        # Place right after <body ...>
        import re
        return re.sub(r"(<body[^>]*>)", r"\\1" + inject, map_html, count=1)
    return inject + map_html


def _map_layout_from_viewport():
    """(is_mobile, iframe_height_px). Uses top-window size + matchMedia (not the eval iframe)."""
    is_mobile = st.session_state.get("_agriscan_map_mobile", False)
    iframe_h = st.session_state.get("_agriscan_map_iframe_h", 620)
    try:
        from streamlit_js_eval import streamlit_js_eval
    except ImportError:
        return is_mobile, iframe_h
    raw = streamlit_js_eval(js_expressions=_MAP_VP_JS, key="agriscan_map_viewport_dims")
    if not raw or not isinstance(raw, str):
        return is_mobile, iframe_h
    try:
        d = json.loads(raw)
        w = float(d["w"])
        h = float(d.get("h") or 700)
        mq = bool(d.get("mobile"))
    except (TypeError, ValueError, KeyError, json.JSONDecodeError):
        return is_mobile, iframe_h
    is_mobile = mq or w <= 768
    if is_mobile:
        # Use ~half the visible viewport for the map chrome (URL bar varies by browser)
        iframe_h = min(720, max(420, int(h * 0.52)))
    else:
        iframe_h = 620
    st.session_state["_agriscan_map_mobile"] = is_mobile
    st.session_state["_agriscan_map_iframe_h"] = iframe_h
    return is_mobile, iframe_h


def _is_mobile_user_agent() -> bool:
    """Best-effort server-side mobile detection (works even when viewport meta/media queries don't)."""
    try:
        ua = st.context.headers.get("User-Agent", "")
    except Exception:
        ua = ""
    ua_l = (ua or "").lower()
    return any(k in ua_l for k in ["mobi", "android", "iphone", "ipad", "ipod", "windows phone"])


@st.cache_data(show_spinner=False)
def get_cached_map_html(filtered_df, user_lat=None, user_lon=None):
    plot_df = filtered_df.dropna(subset=['lat', 'lon'])
    
    if plot_df.empty and (user_lat is None or user_lon is None):
        return "<h3 style='font-family: Inter, sans-serif; padding: 20px;'>No GPS data available for the selected filters.</h3>"

    start_loc = [-0.8, -78.5]
    zoom = 8
    if user_lat is not None and user_lon is not None:
        start_loc = [user_lat, user_lon]
        zoom = 9

    m = folium.Map(location=start_loc, zoom_start=zoom, tiles="cartodbpositron")
    
    if user_lat is not None and user_lon is not None:
        folium.Marker(
            location=[user_lat, user_lon],
            popup="<div style='font-family:Outfit,sans-serif;font-weight:700;'>Your Location</div>",
            icon=folium.Icon(color='blue', icon='user', prefix='fa')
        ).add_to(m)
        
        folium.Circle(
            location=[user_lat, user_lon],
            radius=15000,
            color="#2979ff",
            fill=True,
            fillOpacity=0.1,
            weight=2
        ).add_to(m)

    # Pre-format lists for maximum iteration speed (bypasses pandas iterrows overhead)
    plants = plot_df['plant'].apply(format_label).tolist()
    diseases = plot_df['disease'].apply(format_label).tolist()
    areas = plot_df['area_m2'].tolist()
    severities = plot_df['severity'].tolist()
    dates = plot_df['date'].astype(str).tolist()
    lats = plot_df['lat'].tolist()
    lons = plot_df['lon'].tolist()

    # Iterate via fast python lists rather than pandas DataFrames to build a single JSON payload
    fast_data = []
    for i in range(len(plot_df)):
        popup_text = f"""
        <div style="font-family:Inter,sans-serif;">
            <b style="font-family:Outfit,sans-serif;">Plant:</b> {plants[i]}<br>
            <b style="font-family:Outfit,sans-serif;">Disease:</b> {diseases[i]}<br>
            <b>Area:</b> {areas[i]} m² | <b>Sev:</b> {severities[i]*100:.1f}%<br>
            <span style="font-size:0.8em; opacity:0.7;">{dates[i]}</span>
        </div>
        """
        fast_data.append([lats[i], lons[i], severities[i], popup_text])

    # Compiles directly to JavaScript to bypass Python object bottleneck and websocket crash limits
    callback = """
    function (row) {
        var marker = L.circleMarker(new L.LatLng(row[0], row[1]), {
            radius: 8 + row[2]*10,
            color: '#e74c3c',
            fill: true,
            fillColor: '#e74c3c',
            fillOpacity: 0.7
        });
        marker.bindPopup(row[3], {maxWidth: 200});
        return marker;
    }
    """
    FastMarkerCluster(data=fast_data, callback=callback).add_to(m)

    heat_data = plot_df[["lat","lon","severity"]].values.tolist()
    if heat_data:
        HeatMap(heat_data, radius=12, blur=10, max_zoom=10).add_to(m)

    # Use the full HTML document rather than Folium's notebook iframe wrapper.
    # The iframe wrapper uses its own internal sizing which makes Streamlit height
    # changes appear to have no effect on mobile.
    return m.get_root().render()

def calculate_stats(df, all_df):
    stats = {}
    stats['total'] = len(df)
    
    # 30 day trend approximation
    end_date = df['date'].max() if not df.empty else datetime.date.today()
    if pd.isna(end_date): end_date = datetime.date.today()
    
    cutoff_30 = end_date - datetime.timedelta(days=30)
    cutoff_60 = end_date - datetime.timedelta(days=60)
    
    current_30 = len(df[df['date'] > cutoff_30])
    prior_30 = len(df[(df['date'] > cutoff_60) & (df['date'] <= cutoff_30)])
    
    if prior_30 > 0:
        pct_change = ((current_30 - prior_30) / prior_30) * 100
        stats['trend_str'] = f"<span class='{'trend-up' if pct_change > 0 else 'trend-down'}'>{'↗' if pct_change > 0 else '↘'} {abs(pct_change):.1f}%</span> vs last 30 days"
    else:
        stats['trend_str'] = "<span class='trend-neutral'>+0% vs last 30 days</span>"

    # Region clustering approximation (round to ~10km blocks, 10km = 0.0898 degrees)
    if not df.empty:
        df_coords = df.dropna(subset=['lat', 'lon']).copy()
        if not df_coords.empty:
            df_coords['r_lat'] = (df_coords['lat'] / 0.0898).round() * 0.0898
            df_coords['r_lon'] = (df_coords['lon'] / 0.0898).round() * 0.0898
            region_counts = df_coords.groupby(['r_lat', 'r_lon']).size()
            stats['active_regions'] = len(region_counts)
            stats['highest_cluster_count'] = region_counts.max()
            best_coord = region_counts.idxmax()
            
            # Reverse geocode for the highest cluster
            loc_info = reverse_geocode(best_coord[0], best_coord[1])
            city_name = loc_info.get("city") or loc_info.get("state") or loc_info.get("display_name")
            stats['highest_cluster_name'] = city_name.split(',')[0] if city_name else f"Grid ({best_coord[0]:.1f}, {best_coord[1]:.1f})"
        else:
            stats['active_regions'] = 0
            stats['highest_cluster_count'] = 0
            stats['highest_cluster_name'] = "None"
    else:
        stats['active_regions'] = 0
        stats['highest_cluster_count'] = 0
        stats['highest_cluster_name'] = "None"
        
    stats['avg_per_region'] = int(stats['total'] / stats['active_regions']) if stats['active_regions'] > 0 else 0

    return stats


def map_page():
    st.markdown(_DASHBOARD_CSS, unsafe_allow_html=True)

    _lv = 3
    if st.session_state.get("_agriscan_map_layout_version") != _lv:
        st.session_state["_agriscan_map_layout_version"] = _lv
        st.session_state.pop("_agriscan_map_mobile", None)
        st.session_state.pop("_agriscan_map_iframe_h", None)

    # ── Header ──
    st.markdown("""
        <div class="agriscan-page-title map-header">
            <h1>AgriScan Epidemiological Map</h1>
            <p class="agriscan-page-subtitle">Visualize and monitor crop disease outbreaks across regions in real time.</p>
        </div>
    """, unsafe_allow_html=True)

    # ── Load Data ──
    data = fetch_all_records()
    if data.empty:
        st.warning("No epidemiological data found in the records.")
        return

    # ── Filters Card ──
    with st.container(border=True):
        header_container = st.container()
        
        col_f1, col_f2, col_f3 = st.columns([1, 1, 1])
        with col_f1:
            plant_filter = st.selectbox(
                "Plant Type", ["All"] + sorted(data["plant"].unique().tolist()), 
                key="plant_filter", format_func=lambda x: format_label(x) if x != "All" else "All"
            )
        with col_f2:
            disease_filter = st.selectbox(
                "Disease", ["All"] + sorted(data["disease"].unique().tolist()), 
                key="disease_filter", format_func=lambda x: format_label(x) if x != "All" else "All"
            )
        with col_f3:
            min_date, max_date = data["date"].min(), data["date"].max()
            date_range = st.date_input("Date Range", value=(min_date, max_date), min_value=min_date, max_value=max_date, key="date_filter")
        
        filtered = data.copy()
        if plant_filter != "All": filtered = filtered[filtered["plant"] == plant_filter]
        if disease_filter != "All": filtered = filtered[filtered["disease"] == disease_filter]
        if isinstance(date_range, tuple) and len(date_range) == 2:
            filtered = filtered[(filtered["date"] >= date_range[0]) & (filtered["date"] <= date_range[1])]

        with header_container:
            c_head1, c_head2 = st.columns([5, 1])
            with c_head1:
                st.markdown("<h3 style='margin-top:0; margin-bottom:12px; font-family:Outfit, sans-serif; font-size:1.1rem;'>Filters</h3>", unsafe_allow_html=True)
            with c_head2:
                with st.popover("↓ Export Map", use_container_width=True):
                    csv = filtered.to_csv(index=False)
                    st.download_button("Download CSV", data=csv, file_name="agriscan_data.csv", mime="text/csv", use_container_width=True)
                    if st.button("Generate JPG", use_container_width=True):
                        with st.spinner("Generating..."):
                            m_temp = folium.Map(location=[-0.8, -78.5], zoom_start=8, tiles="cartodbpositron")
                            HeatMap(filtered.dropna(subset=['lat','lon'])[["lat","lon","severity"]].values.tolist(), radius=12, blur=10).add_to(m_temp)
                            m_temp.save("agriscan_map.html")
                            jpg_path = export_map_to_jpg(os.path.abspath("agriscan_map.html"))
                            with open(jpg_path, "rb") as file:
                                st.download_button("Download JPG Ready", data=file, file_name="agriscan_map.jpg", mime="image/jpeg", key="dl_jpg")

        st.markdown(f"""
            <div class="pulse-indicator" style="margin-bottom: 8px;">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#2E7D32" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline></svg>
                Detected outbreaks: <span style="color:#2E7D32;">{len(filtered):,}</span>
            </div>
        """, unsafe_allow_html=True)

    # --- Automatic Geolocation Fetch (so risk card updates without manual reload) ---
    if "geo_lat" not in st.session_state:
        st.session_state.geo_lat = None
    if "geo_lon" not in st.session_state:
        st.session_state.geo_lon = None

    if st.session_state.get("permissions_acknowledged") and callable(get_geolocation):
        # Avoid StreamlitDuplicateElementKey: get_geolocation() defaults to key='getLocation()'
        # so each page must provide a unique component_key.
        loc = get_geolocation(component_key="agriscan_geo_map")
        if loc and isinstance(loc, dict) and "coords" in loc:
            coords = loc.get("coords") or {}
            lat = coords.get("latitude")
            lon = coords.get("longitude")
            if lat is not None and lon is not None:
                st.session_state.geo_lat = lat
                st.session_state.geo_lon = lon

    u_lat = st.session_state.get("geo_lat")
    u_lon = st.session_state.get("geo_lon")
    map_html = _inject_folium_fill_style(get_cached_map_html(filtered, u_lat, u_lon))
    # Prefer UA-based detection (viewport/meta quirks can make media queries never trigger on some deployments).
    is_mobile = _is_mobile_user_agent()
    if is_mobile:
        # Keep map tall enough to be useful but avoid trapping the user (phone screens vary a lot).
        map_iframe_h = 520
    else:
        _, map_iframe_h = _map_layout_from_viewport()

    footer_html = f"""
        <div class="map-footer">
            <span>Last updated: {datetime.datetime.now().strftime('%b %d, %Y %H:%M %p')}</span>
        </div>
        """

    def _render_stats_sidebar():
        stats = calculate_stats(filtered, data)

        u_lat_r = st.session_state.get("geo_lat")
        u_lon_r = st.session_state.get("geo_lon")

        if u_lat_r and u_lon_r and not filtered.empty:
            filtered_copy = filtered.dropna(subset=["lat", "lon"]).copy()
            if not filtered_copy.empty:
                filtered_copy["dist"] = filtered_copy.apply(
                    lambda r: _haversine_km(u_lat_r, u_lon_r, r["lat"], r["lon"]), axis=1
                )
                min_dist = filtered_copy["dist"].min()

                if disease_filter == "All":
                    near_lbl = "Nearest outbreak"
                    mid_lbl = "Outbreaks"
                    low_lbl = "Nearest outbreak"
                else:
                    near_lbl = "Outbreak"
                    mid_lbl = "Cases"
                    low_lbl = "Nearest case"

                if min_dist < 10:
                    r_lvl, r_desc, r_cls = (
                        "High",
                        f"{near_lbl} {min_dist:.1f}km away. Take immediate preventive action.",
                        "high",
                    )
                    r_icn = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>'
                elif min_dist < 50:
                    r_lvl, r_desc, r_cls = (
                        "Moderate",
                        f"{mid_lbl} {min_dist:.1f}km away. Increased monitoring advised.",
                        "mod",
                    )
                    r_icn = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>'
                else:
                    r_lvl, r_desc, r_cls = (
                        "Low",
                        f"{low_lbl} {min_dist:.1f}km away. No immediate threat.",
                        "low",
                    )
                    r_icn = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>'
            else:
                r_lvl, r_desc, r_cls = "Unknown", "No GPS coordinates available for filtered outbreaks.", "unk"
                r_icn = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"></circle><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>'

            st.markdown(
                f"""
            <div class="risk-card">
                <span class="risk-badge {r_cls}">{r_lvl}</span>
                <div class="risk-icon {r_cls}">{r_icn}</div>
                <div style="width: 100%;">
                    <div class="dash-card-title" style="margin:0;">Overall Risk</div>
                    <div style="font-weight:800; font-size:1.3rem; color:var(--text-color); margin-bottom: 4px;">{r_lvl}</div>
                    <div class="dash-card-subtitle" style="line-height:1.4;">{r_desc}</div>
                </div>
            </div>
            """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                """
            <div class="risk-card" style="opacity: 0.7;">
                <div class="risk-icon unk">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"></circle><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>
                </div>
                <div style="width: 100%;">
                    <div class="dash-card-title" style="margin:0;">Overall Risk</div>
                    <div style="font-weight:800; font-size:1.2rem; color:var(--text-color); margin-bottom: 4px;">Location Required</div>
                    <div class="dash-card-subtitle" style="line-height:1.4;">Enable GPS to see your local risk level.</div>
                </div>
            </div>
            """,
                unsafe_allow_html=True,
            )

        st.markdown(f"""
        <div class="dash-card">
            <div class="dash-card-title">Total Outbreaks</div>
            <div class="dash-card-value">{stats['total']:,}</div>
            <div class="dash-card-subtitle">{stats['trend_str']}</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(f"""
        <div class="dash-card">
            <div class="dash-card-title">Highest Cluster</div>
            <div class="dash-card-value">{stats['highest_cluster_count']:,} <span style="font-size:0.8rem; font-weight:500;">cases</span></div>
            <div class="dash-card-subtitle">{stats['highest_cluster_name']}</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(f"""
        <div class="dash-card">
            <div class="dash-card-title">Avg. Cases / 10km</div>
            <div class="dash-card-value">{stats['avg_per_region']:,}</div>
            <div class="dash-card-subtitle">Across active zones</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div class="info-block">
            <div>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#2979ff" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>
            </div>
            <div>
                <b>About this map</b><br>
                Heatmap shows outbreak density by location. Click on a cluster to view details.
            </div>
        </div>
        """, unsafe_allow_html=True)

    def _render_stats_mobile():
        stats = calculate_stats(filtered, data)

        u_lat_r = st.session_state.get("geo_lat")
        u_lon_r = st.session_state.get("geo_lon")

        # Risk first (keep readable; avoid stuffing into a scroll row)
        if u_lat_r and u_lon_r and not filtered.empty:
            filtered_copy = filtered.dropna(subset=["lat", "lon"]).copy()
            if not filtered_copy.empty:
                filtered_copy["dist"] = filtered_copy.apply(
                    lambda r: _haversine_km(u_lat_r, u_lon_r, r["lat"], r["lon"]), axis=1
                )
                min_dist = filtered_copy["dist"].min()

                if disease_filter == "All":
                    near_lbl = "Nearest outbreak"
                    mid_lbl = "Outbreaks"
                    low_lbl = "Nearest outbreak"
                else:
                    near_lbl = "Outbreak"
                    mid_lbl = "Cases"
                    low_lbl = "Nearest case"

                if min_dist < 10:
                    r_lvl, r_desc, r_cls = (
                        "High",
                        f"{near_lbl} {min_dist:.1f}km away. Take immediate preventive action.",
                        "high",
                    )
                    r_icn = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>'
                elif min_dist < 50:
                    r_lvl, r_desc, r_cls = (
                        "Moderate",
                        f"{mid_lbl} {min_dist:.1f}km away. Increased monitoring advised.",
                        "mod",
                    )
                    r_icn = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>'
                else:
                    r_lvl, r_desc, r_cls = (
                        "Low",
                        f"{low_lbl} {min_dist:.1f}km away. No immediate threat.",
                        "low",
                    )
                    r_icn = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>'
            else:
                r_lvl, r_desc, r_cls = "Unknown", "No GPS coordinates available for filtered outbreaks.", "unk"
                r_icn = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"></circle><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>'

            st.markdown(
                f"""
            <div class="risk-card">
                <span class="risk-badge {r_cls}">{r_lvl}</span>
                <div class="risk-icon {r_cls}">{r_icn}</div>
                <div style="width: 100%;">
                    <div class="dash-card-title" style="margin:0;">Overall Risk</div>
                    <div style="font-weight:800; font-size:1.3rem; color:var(--text-color); margin-bottom: 4px;">{r_lvl}</div>
                    <div class="dash-card-subtitle" style="line-height:1.4;">{r_desc}</div>
                </div>
            </div>
            """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                """
            <div class="risk-card" style="opacity: 0.7;">
                <div class="risk-icon unk">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"></circle><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>
                </div>
                <div style="width: 100%;">
                    <div class="dash-card-title" style="margin:0;">Overall Risk</div>
                    <div style="font-weight:800; font-size:1.2rem; color:var(--text-color); margin-bottom: 4px;">Location Required</div>
                    <div class="dash-card-subtitle" style="line-height:1.4;">Enable GPS to see your local risk level.</div>
                </div>
            </div>
            """,
                unsafe_allow_html=True,
            )

        # Metrics row (scrollable)
        st.markdown(
            f"""
        <div class="mobile-card-row" role="region" aria-label="Outbreak metrics">
            <div class="dash-card mobile-card">
                <div class="dash-card-title">Total Outbreaks</div>
                <div class="dash-card-value">{stats['total']:,}</div>
                <div class="dash-card-subtitle">{stats['trend_str']}</div>
            </div>
            <div class="dash-card mobile-card">
                <div class="dash-card-title">Highest Cluster</div>
                <div class="dash-card-value">{stats['highest_cluster_count']:,} <span style="font-size:0.8rem; font-weight:500;">cases</span></div>
                <div class="dash-card-subtitle">{stats['highest_cluster_name']}</div>
            </div>
            <div class="dash-card mobile-card">
                <div class="dash-card-title">Avg. Cases / 10km</div>
                <div class="dash-card-value">{stats['avg_per_region']:,}</div>
                <div class="dash-card-subtitle">Across active zones</div>
            </div>
        </div>
        """,
            unsafe_allow_html=True,
        )

        # About below (full width)
        st.markdown(
            """
        <div class="info-block">
            <div>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#2979ff" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>
            </div>
            <div>
                <b>About this map</b><br>
                Heatmap shows outbreak density by location. Click on a cluster to view details.
            </div>
        </div>
        """,
            unsafe_allow_html=True,
        )

    def _render_stats_desktop_below():
        """Desktop: keep map large, show minicards below in a row."""
        stats = calculate_stats(filtered, data)

        u_lat_r = st.session_state.get("geo_lat")
        u_lon_r = st.session_state.get("geo_lon")

        def _ellipsize(s: str, n: int) -> str:
            s = (s or "").strip()
            return s if len(s) <= n else (s[: max(0, n - 1)].rstrip() + "…")

        # Compute risk content, then render as a compact minicard (same style as others).
        risk_level = "Unknown"
        risk_desc = "No GPS coordinates available for filtered outbreaks."
        risk_cls = "unk"
        risk_icn = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"></circle><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>'
        if u_lat_r and u_lon_r and not filtered.empty:
            filtered_copy = filtered.dropna(subset=["lat", "lon"]).copy()
            if not filtered_copy.empty:
                filtered_copy["dist"] = filtered_copy.apply(
                    lambda r: _haversine_km(u_lat_r, u_lon_r, r["lat"], r["lon"]), axis=1
                )
                min_dist = filtered_copy["dist"].min()

                if disease_filter == "All":
                    near_lbl = "Nearest outbreak"
                    mid_lbl = "Outbreaks"
                    low_lbl = "Nearest outbreak"
                else:
                    near_lbl = "Outbreak"
                    mid_lbl = "Cases"
                    low_lbl = "Nearest case"

                if min_dist < 10:
                    r_lvl, r_desc, r_cls = (
                        "High",
                        f"{near_lbl} {min_dist:.1f}km away. Take immediate preventive action.",
                        "high",
                    )
                    r_icn = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>'
                elif min_dist < 50:
                    r_lvl, r_desc, r_cls = (
                        "Moderate",
                        f"{mid_lbl} {min_dist:.1f}km away. Increased monitoring advised.",
                        "mod",
                    )
                    r_icn = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>'
                else:
                    r_lvl, r_desc, r_cls = (
                        "Low",
                        f"{low_lbl} {min_dist:.1f}km away. No immediate threat.",
                        "low",
                    )
                    r_icn = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>'
                risk_level, risk_desc, risk_cls, risk_icn = r_lvl, r_desc, r_cls, r_icn
            else:
                # keep defaults
                pass
        elif not (u_lat_r and u_lon_r):
            risk_level = "Location Required"
            risk_desc = "Enable GPS to see your local risk level."
            risk_cls = "unk"

        risk_desc = _ellipsize(risk_desc, 92)
        risk_badge = risk_level if risk_level in ["High", "Moderate", "Low"] else "Info"

        # Render as a single grid so cards align cleanly (Streamlit columns don't equalize heights).
        # IMPORTANT: don't indent this HTML block; leading spaces turn it into a Markdown code block.
        st.markdown(
            f"""<div class="desktop-card-row">
  <div class="dash-card dash-card-risk">
    <div class="dash-card-title">Overall Risk</div>
    <div class="dash-card-value" style="font-size: 1.45rem;">{risk_level}</div>
    <div class="dash-card-subtitle">{risk_desc}</div>
    <div class="risk-mini-icon {risk_cls}">{risk_icn}</div>
    <span class="risk-mini-badge {risk_cls}">{risk_badge}</span>
  </div>

  <div class="dash-card">
    <div class="dash-card-title">Total Outbreaks</div>
    <div class="dash-card-value">{stats['total']:,}</div>
    <div class="dash-card-subtitle">{stats['trend_str']}</div>
  </div>

  <div class="dash-card">
    <div class="dash-card-title">Highest Cluster</div>
    <div class="dash-card-value">{stats['highest_cluster_count']:,} <span style="font-size:0.8rem; font-weight:500;">cases</span></div>
    <div class="dash-card-subtitle">{_ellipsize(stats.get('highest_cluster_name') or 'None', 26)}</div>
  </div>

  <div class="dash-card">
    <div class="dash-card-title">Avg. Cases / 10km</div>
    <div class="dash-card-value">{stats['avg_per_region']:,}</div>
    <div class="dash-card-subtitle">Across active zones</div>
  </div>
</div>""",
            unsafe_allow_html=True,
        )

        st.markdown(
            """
        <div class="info-block" style="margin-top: 12px;">
            <div>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#2979ff" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>
            </div>
            <div>
                <b>About this map</b><br>
                Heatmap shows outbreak density by location. Click on a cluster to view details.
            </div>
        </div>
        """,
            unsafe_allow_html=True,
        )

    # ── Layout ──
    # Mobile: always stack minicards below map (no columns) to eliminate "trying to appear to the side".
    if is_mobile:
        components.html(map_html, height=map_iframe_h, scrolling=False)
        st.markdown(footer_html, unsafe_allow_html=True)
        _render_stats_mobile()
        return

    # Desktop: render the map as the primary content, then show minicards below it.
    components.html(map_html, height=map_iframe_h, scrolling=False)
    st.markdown(footer_html, unsafe_allow_html=True)
    _render_stats_desktop_below()

    # ── Temporal Tendency ──
    st.divider()
    # Render inside a keyed container so CSS can scope to this one toggle.
    with st.container(key="tendency_toggle_wrap"):
        col_t_left, col_t_right = st.columns([7, 3], vertical_alignment="bottom")
        with col_t_left:
            st.markdown(
                """
<div class="tendency-header">
  <div class="t-icon" aria-hidden="true">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
      <path d="M3 3v18h18"></path>
      <path d="M7 14l3-3 3 2 5-6"></path>
      <path d="M17 7h3v3"></path>
    </svg>
  </div>
  <div>
    <h3>Temporal tendency</h3>
    <p class="t-desc">Trend over time for your current map filters.</p>
  </div>
</div>
""",
                unsafe_allow_html=True,
            )
        with col_t_right:
            # Keep Streamlit toggle for state; label is short to avoid redundancy.
            with st.container(key="tendency_toggle_right"):
                show_tendency = st.toggle("Show", key="tendency_toggle")

    if show_tendency:
        st.markdown(
            f"""<div class="tendency-body">
  <div style="display:flex; align-items:center; justify-content:space-between; gap:10px; margin-bottom:8px;">
    <div style="font-family:Outfit,sans-serif;font-weight:800;letter-spacing:-0.01em;color:var(--text-color);font-size:1.02rem;">
      Trend analysis
    </div>
    <span class="tendency-chip">{plant_filter if plant_filter != "All" else "All crops"} · {disease_filter if disease_filter != "All" else "All diseases"}</span>
  </div>
""",
            unsafe_allow_html=True,
        )
        if not filtered.empty:
            start_date, end_date = date_range[0], date_range[1]
            all_dates = pd.date_range(start=start_date, end=end_date).date
            daily_counts = filtered.groupby("date").size().reindex(all_dates, fill_value=0)
            cumulative_counts = daily_counts.cumsum()

            fig = make_subplots(specs=[[{"secondary_y": True}]])
            plant_title = plant_filter if plant_filter != "All" else "All Crops"
            disease_title = f" - {disease_filter}" if disease_filter != "All" else ""
            full_title = f"Trend: {plant_title}{disease_title}"

            fig.add_trace(go.Bar(
                x=[d.strftime('%Y-%m-%d') for d in all_dates],
                y=daily_counts,
                name="New Daily Cases",
                marker_color="#e74c3c",
                opacity=0.7
            ), secondary_y=False)

            fig.add_trace(go.Scatter(
                x=[d.strftime('%Y-%m-%d') for d in all_dates],
                y=cumulative_counts,
                name="Cumulative Trend",
                mode="lines+markers",
                line=dict(color="#2c3e50", width=3),
                marker=dict(size=6)
            ), secondary_y=True)

            fig.update_layout(
                title=full_title,
                xaxis_title="Registration Date",
                hovermode="x unified",
                template="plotly_white",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                margin=dict(l=0, r=0, t=50, b=0),
                height=400
            )
            fig.update_yaxes(title_text="New Daily Cases", secondary_y=False)
            fig.update_yaxes(title_text="Cumulative Cases", secondary_y=True, showgrid=False)

            st.plotly_chart(fig, use_container_width=True)
            st.caption(f"Daily incidence (bars) and cumulative progression (line) for **{plant_title}** outbreaks.")
        else:
            st.warning("No data matches the selected filters. Please adjust your criteria to see the tendency.")
        st.markdown("</div>", unsafe_allow_html=True)

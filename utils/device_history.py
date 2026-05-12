"""Device-only history helpers backed by browser localStorage."""

from __future__ import annotations

import json
from typing import Any

from streamlit_js_eval import streamlit_js_eval


HISTORY_KEY = "agriscan_analysis_history_v1"
MAX_HISTORY_ITEMS = 20


def get_device_history(component_key: str = "agriscan_history_read") -> list[dict[str, Any]]:
    raw = streamlit_js_eval(
        js_expressions=(
            f"JSON.parse(localStorage.getItem({json.dumps(HISTORY_KEY)}) || '[]')"
        ),
        key=component_key,
    )
    return raw if isinstance(raw, list) else []


def save_history_record(
    record: dict[str, Any],
    component_key: str = "agriscan_history_save",
) -> bool:
    record_json = json.dumps(record, default=str)
    js = f"""
(function() {{
  const key = {json.dumps(HISTORY_KEY)};
  const incoming = {record_json};
  const maxItems = {MAX_HISTORY_ITEMS};
  let items = [];
  try {{ items = JSON.parse(localStorage.getItem(key) || "[]"); }} catch (e) {{ items = []; }}
  items = items.filter((item) => item && item.id !== incoming.id);
  items.unshift(incoming);
  items = items.slice(0, maxItems);
  localStorage.setItem(key, JSON.stringify(items));
  return true;
}})()
"""
    return bool(streamlit_js_eval(js_expressions=js, key=component_key))


def clear_device_history(component_key: str = "agriscan_history_clear") -> bool:
    return bool(
        streamlit_js_eval(
            js_expressions=f"localStorage.removeItem({json.dumps(HISTORY_KEY)}); true",
            key=component_key,
        )
    )

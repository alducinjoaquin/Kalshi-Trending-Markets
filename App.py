import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timezone, timedelta

st.set_page_config(page_title="Kalshi < 25h", page_icon="📊", layout="wide")

API_URL = "https://api.elections.kalshi.com/trade-api/v2/markets"
LIMIT = 10
MAX_HOURS = 25

st.title(f"Kalshi - {LIMIT} Contratos que vencen en < {MAX_HOURS} horas")
st.caption("Tabla: Mercado | Simbolo | Vencimiento | YES | NO")

@st.cache_data(ttl=60)
def fetch_markets_25h():
    now_ts = int(datetime.now(timezone.utc).timestamp())
    max_ts = int((datetime.now(timezone.utc) + timedelta(hours=MAX_HOURS)).timestamp())
    markets = []
    cursor = ""
    for _ in range(15):
        params = {
            "limit": 200,
            "status": "open",
            "min_close_ts": now_ts,
            "max_close_ts": max_ts
        }
        if cursor:
            params["cursor"] = cursor
        try:
            res = requests.get(API_URL, params=params, timeout=15)
            if res.status_code != 200:
                break
            data = res.json()
            fetched = data.get("markets", [])
            if not fetched:
                break
            markets.extend(fetched)
            cursor = data.get("cursor")
            if not cursor:
                break
        except Exception:
            break
    return markets

def extract_yes_no(m):
    yes = None
    for k in ["yes_bid", "last_price", "yes_ask"]:
        v = m.get(k)
        if v is None:
            continue
        try:
            if isinstance(v, dict):
                v = v.get("cents") or v.get("dollars") or 0
                if isinstance(v, float) and v < 2:
                    v = v * 100
            y = int(float(v))
            if 0 < y < 2 and isinstance(v, float):
                y = int(v * 100)
            if 1 <= y <= 99:
                yes = y
                break
        except:
            continue
    if yes is None:
        yes = 50
    yes = max(1, min(99, yes))
    no = 100 - yes
    return yes, no

if st.button("ACTUALIZAR DATOS", type="primary", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

with st.spinner(f"Buscando mercados que cierran en < {MAX_HOURS}h..."):
    raw = fetch_markets_25h()
    rows = []
    for m in raw:
        raw_time = m.get("close_time") or m.get("expiration_time") or m.get("expected_expiration_time")
        try:
            dt = datetime.fromisoformat(raw_time.replace("Z", "+00:00")) if raw_time else datetime.now(timezone.utc)
            hours_left = (dt - datetime.now(timezone.utc)).total_seconds() / 3600
        except:
            dt = datetime.now(timezone.utc)
            hours_left = 0

        yes_val, no_val = extract_yes_no(m)
        title = (m.get("title") or m.get("subtitle") or "Sin titulo")

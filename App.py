import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timezone

# ============================================================
# CONFIGURACIÓN
# ============================================================

st.set_page_config(
    page_title="Kalshi Trending Markets",
    page_icon="📊",
    layout="wide"
)

API_URL = "https://api.elections.kalshi.com/trade-api/v2/markets"

# ============================================================
# CONSULTA A LA API (Obtiene todos los mercados abiertos)
# ============================================================

@st.cache_data(ttl=300)
def fetch_raw_markets():
    markets = []
    cursor = ""
    
    # 25 páginas para capturar la mayor cantidad de eventos activos
    for _ in range(25):
        params = {"limit": 1000, "status": "open"}
        if cursor:
            params["cursor"] = cursor

        try:
            res = requests.get(API_URL, params=params, timeout=15)
            res.raise_for_status()
            data = res.json()
            fetched = data.get("markets", [])
            markets.extend(fetched)
            cursor = data.get("cursor")
            if not cursor or len(fetched) == 0:
                break
        except Exception:
            break

    return markets

# ============================================================
# HORAS AL VENCIMIENTO
# ============================================================

def get_hours_to_close(close_time_str):
    if not close_time_str:
        return None
    try:
        close_time_str = close_time_str.replace("Z", "+00:00")
        close = datetime.fromisoformat(close_time_str)
        now = datetime.now(timezone.utc)
        return (close - now).total_seconds() / 3600.0
    except Exception:
        return None

# ============================================================
# PROCESAMIENTO SIMPLIFICADO
# ============================================================

def process_markets(markets):
    sports_rows = []
    fin_rows = []

    for m in markets:
        # 1. Vencimiento en 1 a 2 días (0 a 48 horas)
        close_time = m.get("close_time") or m.get("expiration_time")
        hours = get_hours_to_close(close_time)

        if hours is None or hours < 0 or hours > 48:
            continue

        # 2. Requisito de Volumen de operaciones
        volume = float(m.get("volume_24h") or m.get("volume_24h_fp") or m.get("volume") or 0)
        if volume <= 0:
            continue

        # 3. Datos del Mercado
        title = m.get("title") or m.get("subtitle") or m.get("ticker") or "Mercado sin título"
        
        # Precios
        yes_val = m.get("yes_ask") or m.get("yes_bid") or m.get("last_price") or 0
        no_val = m.get("no_ask") or m.get("no_bid") or (100 - yes_val if isinstance(yes_val, (int, float)) and yes_val > 0 else 0)

        row = {
            "Evento": title,
            "Terminación": f"En {hours:.1f} hrs",
            "Valor YES": f"{yes_val}¢" if isinstance(yes_val, (int, float)) else str(yes_val),
            "Valor NO": f"{no_val}¢" if isinstance(no_val, (int, float)) else str(no_val),
            "_vol": volume
        }

        # Categorización por etiqueta nativa de Kalshi o ticker
        category_raw = str(m.get("category", "")).lower()
        ticker_raw = str(m.get("ticker", "")).lower()

        is_sports = any(x in category_raw or x in ticker_raw for x in ["sport", "sports", "nfl", "nba", "mlb", "ncaa"])
        
        if is_sports:
            sports_rows.append(row)
        else:
            fin_rows.append(row)

    # Convertir a DataFrames y ordenar por volumen de mayor a menor
    df_sports = pd.DataFrame(sports_rows)
    if not df_sports.empty:
        df_sports = df_sports.sort_values("_vol", ascending=False).head(10).drop(columns=["_vol"])

    df_fin = pd.DataFrame(fin_rows)
    if not df_fin.empty:
        df_fin = df_fin.sort_values("_vol", ascending=False).head(10).drop(columns=["_vol"])

    return df_sports, df_fin

# ============================================================
# INTERFAZ
# ============================================================

st.title("📊 Kalshi Trending Markets")
st.caption("Mercados activos con mayor volumen y vencimiento entre 0 y 48 horas")

if st.button("🔄 ACTUALIZAR DATOS", use_container_width=True):
    st.cache_data.clear()

with st.spinner("Cargando mercados desde Kalshi..."):
    raw_data = fetch_raw_markets()
    df_sports, df_fin = process_markets(raw_data)

# TABLA 1: DEPORTES
st.header("🏆 Deportes")
if not df_sports.empty:
    st.dataframe(df_sports, use_container_width=True, hide_index=True)
else:
    st.warning("No hay mercados de deportes con volumen activo venciendo en las próximas 48 horas.")

st.divider()

# TABLA 2: FINANZAS Y ECONOMÍA
st.header("📈 Finanzas & Economía")
if not df_fin.empty:
    st.dataframe(df_fin, use_container_width=True, hide_index=True)
else:
    st.warning("No hay mercados de finanzas/economía con volumen activo venciendo en las próximas 48 horas.")

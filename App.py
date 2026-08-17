import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timezone

# ============================================================
# CONFIGURACIÓN DE PÁGINA
# ============================================================

st.set_page_config(
    page_title="Kalshi Trending Markets",
    page_icon="📊",
    layout="wide"
)

API_URL = "https://api.elections.kalshi.com/trade-api/v2/markets"

# ============================================================
# OBTENER MERCADOS DIRECTOS
# ============================================================

@st.cache_data(ttl=300)
def fetch_markets():
    markets = []
    cursor = ""
    
    # Consultar las primeras páginas disponibles
    for _ in range(10):
        params = {"limit": 100, "status": "open"}
        if cursor:
            params["cursor"] = cursor

        try:
            res = requests.get(API_URL, params=params, timeout=10)
            if res.status_code != 200:
                break
            data = res.json()
            fetched = data.get("markets", [])
            markets.extend(fetched)
            
            cursor = data.get("cursor")
            if not cursor or not fetched:
                break
        except Exception:
            break

    return markets

# ============================================================
# CÁLCULO DE HORAS
# ============================================================

def parse_hours(close_str):
    if not close_str:
        return None
    try:
        close_str = close_str.replace("Z", "+00:00")
        close_dt = datetime.fromisoformat(close_str)
        now = datetime.now(timezone.utc)
        diff = (close_dt - now).total_seconds() / 3600.0
        return diff
    except Exception:
        return None

# ============================================================
# PROCESAMIENTO Y CLASIFICACIÓN
# ============================================================

def process_data(markets):
    sports_list = []
    finance_list = []

    for m in markets:
        # 1. Parsing de Vencimiento
        close_time = m.get("close_time") or m.get("expiration_time")
        hours = parse_hours(close_time)

        # Filtro de tiempo: entre 0 y 48 horas (próximos 1-2 días)
        # Si la API entrega horas negativas muy pequeñas (en liquidación), las omitimos
        if hours is None or hours < -1 or hours > 48:
            continue

        # 2. Extracción limpia del nombre del evento
        title = m.get("title") or m.get("subtitle") or m.get("ticker") or "Sin título"
        ticker = str(m.get("ticker", "")).upper()
        category = str(m.get("category", "")).upper()

        # 3. Precios de mercado (Convertir a centavos ¢ o porcentaje)
        yes_price = m.get("yes_bid") or m.get("yes_ask") or m.get("last_price") or 0
        no_price = m.get("no_bid") or m.get("no_ask") or 0
        
        if yes_price == 0 and no_price == 0:
            yes_str = "—"
            no_str = "—"
        else:
            yes_str = f"{yes_price}¢"
            no_str = f"{no_price}¢"

        # Formato de tiempo de terminación
        time_str = f"En {max(0, hours):.1f} hrs" if hours > 0 else "Por vencer"

        row = {
            "Evento": f"{title} ({ticker})",
            "Terminación": time_str,
            "Valor YES": yes_str,
            "Valor NO": no_str,
            "_raw_hours": hours
        }

        # Separación simple por categoría o ticker
        is_sports = any(sp in f"{category} {ticker}".upper() for sp in ["SPORT", "NFL", "NBA", "MLB", "NCAA", "SOCCER", "GAME"])

        if is_sports:
            sports_list.append(row)
        else:
            finance_list.append(row)

    df_sports = pd.DataFrame(sports_list)
    df_finance = pd.DataFrame(finance_list)

    if not df_sports.empty:
        df_sports = df_sports.sort_values("_raw_hours").head(10).drop(columns=["_raw_hours"])
        
    if not df_finance.empty:
        df_finance = df_finance.sort_values("_raw_hours").head(10).drop(columns=["_raw_hours"])

    return df_sports, df_finance

# ============================================================
# INTERFAZ
# ============================================================

st.title("📊 Kalshi Trending Markets")
st.caption("Mercados abiertos con vencimiento en las próximas 48 horas")

if st.button("🔄 ACTUALIZAR DATOS", use_container_width=True):
    st.cache_data.clear()

with st.spinner("Cargando información en tiempo real desde Kalshi..."):
    raw_markets = fetch_markets()
    df_sports, df_fin = process_data(raw_markets)

# TABLA 1: DEPORTES
st.header("🏆 Deportes")
if not df_sports.empty:
    st.dataframe(df_sports, use_container_width=True, hide_index=True)
else:
    st.info("No se encontraron eventos deportivos abiertos con vencimiento menor a 48 horas en este momento.")

st.divider()

# TABLA 2: FINANZAS Y ECONOMÍA
st.header("📈 Finanzas & Economía")
if not df_fin.empty:
    st.dataframe(df_fin, use_container_width=True, hide_index=True)
else:
    st.info("No se encontraron mercados de finanzas/economía con vencimiento menor a 48 horas en este momento.")

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
# OBTENER DATOS DE LA API
# ============================================================
@st.cache_data(ttl=180)
def fetch_all_open_markets():
    markets = []
    cursor = ""
    
    # Obtenemos hasta 3,000 mercados abiertos para asegurar inventario
    for _ in range(15):
        params = {"limit": 200, "status": "open"}
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
# CÁLCULO DE VENCIMIENTO
# ============================================================
def process_market_row(m, min_hours, max_hours):
    # Obtención de fecha de expiración/cierre
    raw_time = m.get("close_time") or m.get("expiration_time") or m.get("expected_expiration_time")
    if not raw_time:
        return None

    try:
        dt = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        hours_diff = (dt - now).total_seconds() / 3600.0
        
        # Filtrado por ventana de horas
        if hours_diff < min_hours or hours_diff > max_hours:
            return None

        # Formato de fecha legible
        formatted_date = dt.strftime("%b %d @ %I:%M%p").replace(" 0", " ")
    except Exception:
        return None

    # Extracción de Nombres y Títulos sin contaminación
    title = m.get("title") or "Sin título"
    
    # Limpieza del Símbolo / Nombre principal
    symbol = m.get("event_ticker") or m.get("series_ticker") or m.get("ticker") or "KALSHI"
    symbol_clean = str(symbol).replace("_", " ").upper()

    # Precios YES / NO
    yes_price = m.get("last_price") or m.get("yes_bid") or m.get("yes_ask") or 0
    try:
        yes_val = int(yes_price)
    except (ValueError, TypeError):
        yes_val = 0

    yes_val = max(1, min(99, yes_val)) if yes_val > 0 else 50
    no_val = 100 - yes_val

    return {
        "Mercado / Descripción breve": title,
        "Símbolo / Nombre": symbol_clean,
        "Fecha de vencimiento": formatted_date,
        "YES (valor)": f"{yes_val}%",
        "NO (valor)": f"{no_val}%",
        "_hours": hours_diff
    }

# ============================================================
# INTERFAZ Y FILTROS
# ============================================================
st.title("📊 Kalshi Trending Markets")

# Barra lateral para ajustar ventana de horas en tiempo real
st.sidebar.header("Filtros de Expiración")
min_h, max_h = st.sidebar.slider(
    "Selecciona la ventana de vencimiento (Horas):",
    min_value=0,
    max_value=120,
    value=(0, 72),
    step=6
)

if st.button("🔄 ACTUALIZAR DATOS", use_container_width=True):
    st.cache_data.clear()

with st.spinner("Conectando con Kalshi y extrayendo mercados..."):
    raw_markets = fetch_all_open_markets()
    
    processed_rows = []
    for m in raw_markets:
        row = process_market_row(m, min_h, max_h)
        if row:
            processed_rows.append(row)

    if processed_rows:
        df = pd.DataFrame(processed_rows)
        df = df.sort_values("_hours").drop(columns=["_hours"])
        
        st.caption(f"Mostrando {len(df)} mercados que vencen entre las próximas {min_h} y {max_h} horas.")
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.warning(f"No se encontraron mercados con vencimiento entre {min_h} y {max_h} horas. Prueba amplificando el rango en la barra lateral.")

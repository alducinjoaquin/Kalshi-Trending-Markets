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

# Endpoint de Eventos para evitar la contaminación de títulos
EVENTS_URL = "https://api.elections.kalshi.com/trade-api/v2/events"

# ============================================================
# OBTENER EVENTOS Y MERCADOS LIMPIOS
# ============================================================

@st.cache_data(ttl=300)
def fetch_clean_events():
    events_data = []
    cursor = ""
    
    for _ in range(10):
        params = {"limit": 100, "status": "open", "with_nested_markets": "true"}
        if cursor:
            params["cursor"] = cursor

        try:
            res = requests.get(EVENTS_URL, params=params, timeout=15)
            if res.status_code != 200:
                break
            data = res.json()
            fetched = data.get("events", [])
            events_data.extend(fetched)
            
            cursor = data.get("cursor")
            if not cursor or not fetched:
                break
        except Exception:
            break

    return events_data

# ============================================================
# FORMATO DE FECHA / VENCIMIENTO
# ============================================================

def format_expiration(date_str):
    if not date_str:
        return None, "N/A"
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        hours_diff = (dt - now).total_seconds() / 3600.0
        
        # Formato exacto a la imagen: "Aug 14 @ 2:00PM"
        formatted_str = dt.strftime("%b %d @ %I:%M%p").replace(" 0", " ")
        return hours_diff, formatted_str
    except Exception:
        return None, "N/A"

# ============================================================
# PROCESAR Y CONSTRUIR TABLA EXACTA
# ============================================================

def build_exact_table(events):
    rows = []

    for event in events:
        category_name = str(event.get("category", "")).upper()
        event_title = event.get("title") or event.get("sub_title") or "EVENTO"
        markets = event.get("markets", [])

        for m in markets:
            # 1. Ignorar basura de hibridados "MULTIGAME" o "CROSSCATEGORY"
            ticker = str(m.get("ticker", "")).upper()
            if "MULTIGAME" in ticker or "CROSSCATEGORY" in ticker:
                continue

            # 2. Vencimiento estricto en 1 a 2 días (24 a 48 horas)
            close_time = m.get("close_time") or m.get("expiration_time")
            hours, date_formatted = format_expiration(close_time)

            if hours is None or hours < 24 or hours > 48:
                continue

            # 3. Mapeo exacto de columnas según la imagen:
            # - Mercado / Descripción breve
            desc = m.get("title") or m.get("subtitle") or event_title
            
            # - Símbolo / Nombre
            symbol = event_title.upper()

            # - Precios YES / NO en Porcentaje (%)
            yes_price = m.get("last_price") or m.get("yes_bid") or m.get("yes_ask") or 0
            try:
                yes_val = int(yes_price)
            except (ValueError, TypeError):
                yes_val = 0

            # Normalizar a %
            yes_val = max(1, min(99, yes_val)) if yes_val > 0 else 50
            no_val = 100 - yes_val

            rows.append({
                "Mercado / Descripción breve": desc,
                "Símbolo / Nombre": symbol,
                "Fecha de vencimiento": date_formatted,
                "YES (valor)": f"{yes_val}%",
                "NO (valor)": f"{no_val}%",
                "_hours": hours
            })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("_hours").drop(columns=["_hours"])
    return df

# ============================================================
# INTERFAZ DE USUARIO
# ============================================================

st.title("📊 Kalshi Trending Markets")
st.caption("Mercados con vencimiento exacto entre 24 y 48 horas (1 a 2 días)")

if st.button("🔄 ACTUALIZAR DATOS", use_container_width=True):
    st.cache_data.clear()

with st.spinner("Cargando mercados organizados por eventos..."):
    raw_events = fetch_clean_events()
    df_final = build_exact_table(raw_events)

if not df_final.empty:
    st.dataframe(
        df_final,
        use_container_width=True,
        hide_index=True
    )
else:
    st.warning("No hay eventos activos con vencimiento exacto en la ventana de 24 a 48 horas en este momento.")

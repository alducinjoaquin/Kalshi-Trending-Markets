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
# CONSULTA A LA API
# ============================================================

@st.cache_data(ttl=300)
def fetch_raw_markets():
    markets = []
    cursor = ""
    
    for _ in range(15):
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
# HELPER DE TIEMPO
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
# FILTRADO Y CLASIFICACIÓN ESTRICTA
# ============================================================

def process_sports_markets(markets):
    # Exclusivamente NFL, NCAA Football, NBA, MLB
    sports_keys = ["nfl", "ncaa", "college football", "ncaaf", "nba", "mlb"]
    rows = []

    for m in markets:
        ticker = str(m.get("ticker", "")).lower()
        title = str(m.get("title", "")).lower()
        sub = str(m.get("subtitle", "")).lower()
        category = str(m.get("category", "")).lower()

        text_block = f"{ticker} {title} {sub} {category}"

        # Validar si pertenece a los deportes permitidos
        if not any(k in text_block for k in sports_keys):
            continue

        # Validar vencimiento (1 a 2 días: 0 a 48h)
        hours = get_hours_to_close(m.get("close_time") or m.get("expiration_time"))
        if hours is None or hours < 0 or hours > 48:
            continue

        # Formatear datos limpios
        event_name = m.get("title") or m.get("subtitle") or m.get("ticker")
        yes_price = m.get("yes_ask") or m.get("yes_bid") or 0
        no_price = m.get("no_ask") or m.get("no_bid") or 0
        volume = float(m.get("volume_24h") or m.get("volume") or 0)

        rows.append({
            "Evento": event_name,
            "Terminación": f"En {hours:.1f} hrs",
            "Valor YES": f"{yes_price}¢" if isinstance(yes_price, (int, float)) else str(yes_price),
            "Valor NO": f"{no_price}¢" if isinstance(no_price, (int, float)) else str(no_price),
            "_vol": volume
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("_vol", ascending=False).head(10).drop(columns=["_vol"])
    return df


def process_finance_econ_markets(markets):
    # Finanzas y Economía
    fin_keys = ["fed", "cpi", "gdp", "jobs", "inflation", "rate", "treasury", "s&p", "sp500", "nasdaq", "dow", "btc", "bitcoin", "eth", "nvda", "aapl", "tsla"]
    # Excluir explícitamente cualquier cosa deportiva
    sports_exclude = ["nfl", "nba", "mlb", "game", "match", "vs"]
    rows = []

    for m in markets:
        ticker = str(m.get("ticker", "")).lower()
        title = str(m.get("title", "")).lower()
        sub = str(m.get("subtitle", "")).lower()
        category = str(m.get("category", "")).lower()

        text_block = f"{ticker} {title} {sub} {category}"

        if any(ex in text_block for ex in sports_exclude):
            continue

        if not any(k in text_block for k in fin_keys):
            continue

        hours = get_hours_to_close(m.get("close_time") or m.get("expiration_time"))
        if hours is None or hours < 0 or hours > 48:
            continue

        event_name = m.get("title") or m.get("subtitle") or m.get("ticker")
        yes_price = m.get("yes_ask") or m.get("yes_bid") or 0
        no_price = m.get("no_ask") or m.get("no_bid") or 0
        volume = float(m.get("volume_24h") or m.get("volume") or 0)

        rows.append({
            "Evento": event_name,
            "Terminación": f"En {hours:.1f} hrs",
            "Valor YES": f"{yes_price}¢" if isinstance(yes_price, (int, float)) else str(yes_price),
            "Valor NO": f"{no_price}¢" if isinstance(no_price, (int, float)) else str(no_price),
            "_vol": volume
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("_vol", ascending=False).head(10).drop(columns=["_vol"])
    return df

# ============================================================
# INTERFAZ PRINCIPAL
# ============================================================

st.title("📊 Kalshi Trending Markets")
st.caption("Top 10 mercados con vencimiento en las próximas 48 horas (1-2 días)")

if st.button("🔄 ACTUALIZAR DATOS", use_container_width=True):
    st.cache_data.clear()

with st.spinner("Cargando mercados actualizados desde Kalshi..."):
    raw_data = fetch_raw_markets()
    df_sports = process_sports_markets(raw_data)
    df_fin = process_finance_econ_markets(raw_data)

# TABLA 1: DEPORTES
st.header("🏆 Deportes (NFL, NCAA, NBA, MLB)")
if not df_sports.empty:
    st.dataframe(df_sports, use_container_width=True, hide_index=True)
else:
    st.info("No hay eventos de NFL, NCAA, NBA o MLB programados con vencimiento en las próximas 24-48 horas.")

st.divider()

# TABLA 2: FINANZAS Y ECONOMÍA
st.header("📈 Finanzas & Economía")
if not df_fin.empty:
    st.dataframe(df_fin, use_container_width=True, hide_index=True)
else:
    st.info("No hay eventos de Finanzas o Economía con vencimiento en las próximas 24-48 horas.")

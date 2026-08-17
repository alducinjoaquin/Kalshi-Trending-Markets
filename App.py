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
# OBTENER MERCADOS
# ============================================================

@st.cache_data(ttl=300)
def get_markets():
    markets = []
    cursor = ""

    # Se amplía a 20 páginas para cubrir mayor volumen de mercados
    for _ in range(20):
        params = {
            "limit": 1000,
            "status": "open"
        }

        if cursor:
            params["cursor"] = cursor

        try:
            response = requests.get(API_URL, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            fetched = data.get("markets", [])
            markets.extend(fetched)

            cursor = data.get("cursor")
            if not cursor or len(fetched) == 0:
                break
        except Exception:
            break

    return markets

# ============================================================
# HORAS HASTA EL VENCIMIENTO
# ============================================================

def hours_to_close(close_time_str):
    if not close_time_str:
        return None
    try:
        # Formato ISO flexible
        close_time_str = close_time_str.replace("Z", "+00:00")
        close = datetime.fromisoformat(close_time_str)
        now = datetime.now(timezone.utc)
        return (close - now).total_seconds() / 3600.0
    except Exception:
        return None

# ============================================================
# CLASIFICACIÓN
# ============================================================

def get_category(market):
    text = (
        str(market.get("title", "")) + " " +
        str(market.get("subtitle", "")) + " " +
        str(market.get("ticker", "")) + " " +
        str(market.get("category", ""))
    ).lower()

    sports_words = [
        "nfl", "nba", "wnba", "nhl", "mlb", "soccer", "football", 
        "baseball", "basketball", "hockey", "tennis", "golf", "ufc", 
        "boxing", "match", "game", "team", "league", "championship", "vs"
    ]

    finance_words = [
        "bitcoin", "btc", "ethereum", "eth", "crypto", "stock", "stocks", 
        "nasdaq", "s&p", "sp500", "dow", "earnings", "gold", "silver", 
        "oil", "finance", "financial", "market", "nvda", "aapl", "tsla"
    ]

    economy_words = [
        "fed", "federal reserve", "inflation", "cpi", "gdp", "jobs", 
        "employment", "unemployment", "interest rate", "interest rates", 
        "recession", "economy", "economic", "tariff", "treasury", "ppi"
    ]

    if any(word in text for word in sports_words):
        return "Deportes"
    if any(word in text for word in finance_words):
        return "Finanzas"
    if any(word in text for word in economy_words):
        return "Economía"

    return None

# ============================================================
# PREPARAR DATOS
# ============================================================

def prepare_data(markets):
    rows = []

    for market in markets:
        # 1. Filtro de estado
        status = market.get("status", "").lower()
        if status not in ["open", "active"]:
            continue

        # 2. Filtro de vencimiento (0 a 48 horas = vencimiento en 1 o 2 días)
        close_time = market.get("close_time") or market.get("expiration_time")
        hours = hours_to_close(close_time)

        if hours is None or hours < 0 or hours > 48:
            continue

        # 3. Categorización
        category = get_category(market)
        if category is None:
            continue

        # 4. Extracción segura de valores
        title = market.get("title") or market.get("subtitle") or market.get("ticker") or "Sin nombre"

        # Compatibilidad de campos de precio/volumen según API v2
        yes_bid = market.get("yes_bid") or market.get("yes_bid_dollars") or 0
        yes_ask = market.get("yes_ask") or market.get("yes_ask_dollars") or 0
        no_bid = market.get("no_bid") or market.get("no_bid_dollars") or 0
        no_ask = market.get("no_ask") or market.get("no_ask_dollars") or 0

        volume = market.get("volume_24h") or market.get("volume_24h_fp") or market.get("volume") or 0
        open_interest = market.get("open_interest") or market.get("open_interest_fp") or 0

        try:
            volume = float(volume)
            open_interest = float(open_interest)
        except ValueError:
            volume = 0.0
            open_interest = 0.0

        rows.append({
            "Categoría": category,
            "Mercado": title,
            "YES Bid": yes_bid,
            "YES Ask": yes_ask,
            "NO Bid": no_bid,
            "NO Ask": no_ask,
            "Volumen 24h": volume,
            "Open Interest": open_interest,
            "Horas": hours
        })

    return pd.DataFrame(rows)

# ============================================================
# FORMATO DE TABLA
# ============================================================

def format_table(df):
    result = df.copy()
    if result.empty:
        return result

    price_columns = ["YES Bid", "YES Ask", "NO Bid", "NO Ask"]
    for col in price_columns:
        result[col] = result[col].apply(lambda x: f"{float(x):.2f}" if pd.notna(x) and x != 0 else "—")

    result["Volumen 24h"] = result["Volumen 24h"].apply(lambda x: f"{float(x):,.0f}")
    result["Open Interest"] = result["Open Interest"].apply(lambda x: f"{float(x):,.0f}")
    result["Horas"] = result["Horas"].apply(lambda x: f"{float(x):.1f} h")

    return result

# ============================================================
# INTERFAZ
# ============================================================

st.title("📊 Kalshi Trending Markets")
st.caption("Top mercados por volumen con vencimiento en las próximas 48 horas")

if st.button("🔄 REFRESH", use_container_width=True):
    st.cache_data.clear()

with st.spinner("Consultando mercados de Kalshi..."):
    raw_markets = get_markets()
    df = prepare_data(raw_markets)

if df.empty:
    st.warning("No se encontraron mercados que cumplan con las condiciones en este momento.")
else:
    st.success(f"Se encontraron {len(df)} mercados en total.")

    categories = [
        ("📈 Economía — Top 10", "Economía"),
        ("💰 Finanzas — Top 10", "Finanzas"),
        ("🏆 Deportes — Top 10", "Deportes")
    ]

    for title, cat_name in categories:
        sub_df = df[df["Categoría"] == cat_name].copy()
        
        if not sub_df.empty:
            sub_df = sub_df.sort_values("Volumen 24h", ascending=False).head(10)
            st.subheader(title)
            
            formatted_df = sub_df.drop(columns=["Categoría"])
            formatted_df.insert(0, "#", range(1, len(formatted_df) + 1))
            formatted_df = format_table(formatted_df)
            
            st.dataframe(formatted_df, use_container_width=True, hide_index=True)

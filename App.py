import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timezone

# ============================================================
# CONFIGURACIÓN
# ============================================================
st.set_page_config(
    page_title="Kalshi - Vence < 25h",
    page_icon="📊",
    layout="wide"
)

API_URL = "https://api.elections.kalshi.com/trade-api/v2/markets"
MAX_HOURS = 25
LIMIT_CONTRACTS = 10

st.title("📊 Kalshi - 10 Contratos que vencen en < 25 horas")
st.caption("Tabla con tu diseño: Mercado | Símbolo | Vencimiento | YES | NO")

# ============================================================
# API
# ============================================================
@st.cache_data(ttl=120)
def fetch_all_open_markets():
    markets = []
    cursor = ""
    headers = {"Accept": "application/json"}

    for _ in range(20): # hasta 4000 mercados para asegurar que encontramos 10
        params = {"limit": 200, "status": "open"}
        if cursor:
            params["cursor"] = cursor
        try:
            res = requests.get(API_URL, params=params, headers=headers, timeout=15)
            res.raise_for_status()
            data = res.json()
            fetched = data.get("markets", [])
            if not fetched:
                break
            markets.extend(fetched)
            cursor = data.get("cursor")
            if not cursor:
                break
            # Early exit si ya tenemos suficientes candidatos
            if len(markets) > 2000:
                # seguimos filtrando después, pero evitamos pedir de más
                pass
        except Exception as e:
            st.error(f"Error API Kalshi: {e}")
            break
    return markets

def get_hours_to_expire(market):
    raw_time = market.get("close_time") or market.get("expiration_time") or market.get("expected_expiration_time")
    if not raw_time:
        return None, None
    try:
        dt = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        hours_diff = (dt - now).total_seconds() / 3600.0
        return hours_diff, dt
    except Exception:
        return None, None

def get_yes_price(market):
    # Kalshi devuelve precios en centavos 0-100
    for key in ["yes_bid", "yes_ask", "last_price", "yes_price"]:
        val = market.get(key)
        if val is not None:
            try:
                # Algunos vienen como dict o string
                if isinstance(val, dict):
                    val = val.get("dollars") or val.get("cents") or 0
                iv = int(float(val))
                if 1 <= iv <= 100:
                    return iv
            except:
                continue
    return None

# ============================================================
# PROCESAMIENTO
# ============================================================
def build_table():
    raw_markets = fetch_all_open_markets()
    rows = []

    for m in raw_markets:
        hours, dt = get_hours_to_expire(m)
        if hours is None:
            continue
        if hours <= 0 or hours > MAX_HOURS: # FILTRO < 25 HORAS
            continue

        yes_val = get_yes_price(m)
        if yes_val is None:
            continue

        yes_val = max(1, min(99, yes_val))
        no_val = 100 - yes_val

        title = (m.get("title") or m.get("subtitle") or "Sin título").strip()
        # Descripción breve como en tu foto
        if len(title) > 80:
            title = title[:77] + "..."

        symbol = m.get("event_ticker") or m.get("series_ticker") or m.get("ticker") or "KALSHI"
        symbol_clean = str(symbol).replace("_", " ").upper()

        formatted_date = dt.astimezone(timezone.utc).strftime("%b %d @ %I:%M%p %Z")

        rows.append({
            "Mercado / Descripción breve": title,
            "Símbolo / Nombre": symbol_clean,
            "Fecha de vencimiento": formatted_date,
            "YES (valor)": yes_val,
            "NO (valor)": no_val,
            "_hours": hours,
            "_dt": dt,
            "_vol": m.get("volume", 0)
        })

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df = df.sort_values(by="_hours", ascending=True).head(LIMIT_CONTRACTS)
    return df

# ============================================================
# UI
# ============================================================
col1, col2 = st.columns([1, 4])
with col1:
    if st.button("🔄 ACTUALIZAR", use_container_width=True, type="primary"):
        st.cache_data.clear()
        st.rerun()
with col2:
    st.info(f"Mostrando exactamente {LIMIT_CONTRACTS} contratos con vencimiento < {MAX_HOURS}h, ordenados del más próximo a vencer.")

with st.spinner("Buscando mercados que vencen en < 25h..."):
    df_raw = build_table()

if df_raw.empty:
    st.warning(f"No se encontraron {LIMIT_CONTRACTS} mercados que venzan en < {MAX_HOURS}h. La API puede estar lenta. Dale a ACTUALIZAR.")
else:
    # Tabla final con tu diseño exacto
    df_display = df_raw[["Mercado / Descripción breve", "Símbolo / Nombre", "Fecha de vencimiento", "YES (valor)", "NO (valor)"]].copy()

    # Formateo visual para que se vea como tu foto
    df_display["YES (valor)"] = df_display["YES (valor)"].apply(lambda x: f"{x}%")
    df_display["NO (valor)"] = df_display["NO (valor)"].apply(lambda x: f"{x}%")

    st.dataframe(
        df_display,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Mercado / Descripción breve": st.column_config.TextColumn(width="large"),
            "Símbolo / Nombre": st.column_config.TextColumn(width="medium"),
            "Fecha de vencimiento": st.column_config.TextColumn(width="medium"),
            "YES (valor)": st.column_config.TextColumn("YES", width="small"),
            "NO (valor)": st.column_config.TextColumn("NO", width="small"),
        }
    )

    # Métrica extra útil
    st.caption(f"Vencimiento más cercano: {df_raw.iloc[0]['_hours']:.1f}h | Más lejano de los 10: {df_raw.iloc[-1]['_hours']:.1f}h | Vol total: ${int(df_raw['_vol'].sum()):,}")

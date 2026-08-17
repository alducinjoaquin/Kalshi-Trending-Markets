import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timezone, timedelta
import time

st.set_page_config(page_title="Kalshi < 25h", page_icon="📊", layout="wide")

API_URL = "https://api.elections.kalshi.com/trade-api/v2/markets"
LIMIT = 10
MAX_HOURS = 25

st.title(f"📊 Kalshi - {LIMIT} Contratos que vencen en < {MAX_HOURS} horas")

# ============================================================
# API CORREGIDA - USA FILTRO DE SERVIDOR
# ============================================================
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
            if res.status_code!= 200:
                st.error(f"Kalshi API {res.status_code}: {res.text[:300]}")
                break

            data = res.json()
            fetched = data.get("markets", [])
            markets.extend(fetched)

            cursor = data.get("cursor")
            if not cursor or len(markets) >= 500: # con 500 ya tenemos de sobra para sacar 10
                break
        except Exception as e:
            st.error(f"Error de conexión: {e}")
            break

    return markets

def extract_yes_no(m):
    # Orden correcto según docs: yes_bid es el real, yes_ask es oferta, last_price es último trade
    # Todos vienen en centavos 0-100
    yes = None
    for k in ["yes_bid", "last_price", "yes_ask", "yes_price_dollars"]:
        v = m.get(k)
        if v is None:
            continue
        try:
            # a veces viene como {"cents": 34} o float
            if isinstance(v, dict):
                v = v.get("cents") or v.get("dollars") or 0
                if isinstance(v, float) and v < 2: # si viene en dolares 0.34
                    v = v * 100
            y = int(float(v))
            if y <= 1 and isinstance(v, float): # 0.34 -> 34
                y = int(v * 100)
            if 1 <= y <= 99:
                yes = y
                break
        except:
            continue

    if yes is None:
        yes = 50 # fallback para no descartar el mercado

    return max(1, min(99, yes)), 100 - max(1, min(99, yes))

# ============================================================
# UI
# ============================================================
if st.button("🔄 ACTUALIZAR DATOS", type="primary", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

with st.spinner(f"Buscando en Kalshi todos los mercados que cierran en < {MAX_HOURS}h..."):
    raw = fetch_markets_25h()
    st.caption(f"API devolvió {len(raw)} mercados candidatos en ventana <25h")

    rows = []
    for m in raw:
        raw_time = m.get("close_time") or m.get("expiration_time")
        try:
            dt = datetime.fromisoformat(raw_time.replace("Z", "+00:00")) if raw_time else datetime.now(timezone.utc)
            hours_left = (dt - datetime.now(timezone.utc)).total_seconds() / 3600
        except:
            hours_left = 0
            dt = datetime.now(timezone.utc)

        yes_val, no_val = extract_yes_no(m)

        rows.append({
            "Mercado / Descripción breve": (m.get("title") or m.get("subtitle") or "Sin título")[:90],
            "Símbolo / Nombre": (m.get("ticker") or m.get("event_ticker") or "KALSHI").replace("_"," ")[:25],
            "Fecha de vencimiento": dt.strftime("%b %d @ %I:%M %p UTC"),
            "YES (valor)": yes_val,
            "NO (valor)": no_val,
            "_hours": hours_left,
            "_vol": m.get("volume", 0)
        })

    if rows:
        df = pd.DataFrame(rows).sort_values("_hours").head(LIMIT)

        # Formato final EXACTO como pediste
        df_show = df.copy()
        df_show["YES (valor)"] = df_show["YES (valor)"].apply(lambda x: f"{x}%")
        df_show["NO (valor)"] = df_show["NO (valor)"].apply(lambda x: f"{x}%")

        st.dataframe(
            df_show[["Mercado / Descripción breve", "Símbolo / Nombre", "Fecha de vencimiento", "YES (valor)", "NO (valor)"]],
            use_container_width=True,
            hide_index=True
        )
        st.success(f"✅ Listo: {len(df)} mercados mostrados. El más próximo vence en {df.iloc[0]['_hours']:.2f} horas")
    else:
        st.warning("La API no devolvió

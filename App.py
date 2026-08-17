import streamlit as st
import requests

st.set_page_config(
    page_title="Kalshi Trending Markets",
    layout="wide"
)

st.title("Kalshi Trending Markets")
st.write("Prueba de conexión con la API pública de Kalshi")

if st.button("🔄 REFRESH"):
    url = "https://api.elections.kalshi.com/trade-api/v2/markets"

    params = {
        "limit": 10,
        "status": "open"
    }

    try:
        response = requests.get(url, params=params, timeout=20)
        response.raise_for_status()

        data = response.json()
        markets = data.get("markets", [])

        st.success(f"Conexión correcta. Mercados recibidos: {len(markets)}")

        for market in markets:
            st.write(
                market.get("title")
                or market.get("subtitle")
                or market.get("ticker")
            )

    except Exception as e:
        st.error(f"Error de conexión: {e}")

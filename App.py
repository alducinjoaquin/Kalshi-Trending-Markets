import streamlit as st
import requests
import pandas as pd

st.set_page_config(
    page_title="Kalshi API Test",
    layout="wide"
)

URL = "https://api.elections.kalshi.com/trade-api/v2/markets"

st.title("🔎 Diagnóstico Kalshi")

if st.button("🔄 CONSULTAR KALSHI", type="primary"):

    try:

        response = requests.get(
            URL,
            params={
                "limit": 10,
                "status": "open"
            },
            timeout=30
        )

        st.write("HTTP:", response.status_code)

        data = response.json()

        markets = data.get("markets", [])

        st.write(
            "Mercados recibidos:",
            len(markets)
        )

        if markets:

            st.subheader("Primer mercado recibido")

            m = markets[0]

            st.json(m)

            st.subheader("Campos importantes")

            test = {
                "ticker": m.get("ticker"),
                "title": m.get("title"),
                "status": m.get("status"),
                "close_time": m.get("close_time"),
                "expiration_time": m.get("expiration_time"),
                "expected_expiration_time":
                    m.get("expected_expiration_time"),
                "yes_bid": m.get("yes_bid"),
                "yes_bid_dollars":
                    m.get("yes_bid_dollars"),
                "no_bid": m.get("no_bid"),
                "no_bid_dollars":
                    m.get("no_bid_dollars"),
                "volume_24h":
                    m.get("volume_24h"),
                "volume_24h_fp":
                    m.get("volume_24h_fp")
            }

            st.dataframe(
                pd.DataFrame(
                    [test]
                ),
                use_container_width=True
            )

    except Exception as e:

        st.error(
            f"Error: {e}"
        )

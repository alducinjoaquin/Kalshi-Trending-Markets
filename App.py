import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timezone

st.set_page_config(
    page_title="Kalshi Trending",
    page_icon="📊",
    layout="wide"
)

API = "https://api.elections.kalshi.com/trade-api/v2/markets"

st.title("📊 Kalshi Trending Markets")
st.caption("Mercados con vencimiento entre 24 y 48 horas")

# --------------------------------------------------
# FUNCIONES
# --------------------------------------------------

def get_markets():

    markets = []
    cursor = ""

    for _ in range(10):

        params = {
            "limit": 1000,
            "status": "open"
        }

        if cursor:
            params["cursor"] = cursor

        response = requests.get(
            API,
            params=params,
            timeout=30
        )

        response.raise_for_status()

        data = response.json()

        markets.extend(data.get("markets", []))

        cursor = data.get("cursor")

        if not cursor:
            break

    return markets


def hours_to_close(close_time):

    try:
        close = datetime.fromisoformat(
            close_time.replace("Z", "+00:00")
        )

        now = datetime.now(timezone.utc)

        return (close - now).total_seconds() / 3600

    except:
        return None


def category(market):

    text = (
        str(market.get("title", "")) +
        " " +
        str(market.get("subtitle", "")) +
        " " +
        str(market.get("ticker", ""))
    ).lower()

    sports_words = [
        "nfl", "nba", "wnba", "nhl", "mlb",
        "soccer", "football", "baseball",
        "basketball", "hockey", "tennis",
        "golf", "ufc", "boxing",
        "match", "game", "team"
    ]

    finance_words = [
        "bitcoin", "ethereum", "crypto",
        "stock", "stocks", "nasdaq",
        "s&p", "dow", "earnings",
        "gold", "oil", "finance",
        "financial", "market"
    ]

    economy_words = [
        "fed", "federal reserve",
        "inflation", "cpi", "gdp",
        "jobs", "unemployment",
        "interest rate", "recession",
        "economy", "economic",
        "tariff", "treasury"
    ]

    if any(word in text for word in sports_words):
        return "Deportes"

    if any(word in text for word in finance_words):
        return "Finanzas"

    if any(word in text for word in economy_words):
        return "Economía"

    return None


def prepare_data(markets):

    rows = []

    for m in markets:

        hours = hours_to_close(
            m.get("close_time", "")
        )

        if hours is None:
            continue

        # Solo 24–48 horas
        if hours < 24 or hours > 48:
            continue

        cat = category(m)

        if cat is None:
            continue

        rows.append({
            "Categoría": cat,
            "Mercado": (
                m.get("title")
                or m.get("subtitle")
                or m.get("ticker")
            ),
            "YES": m.get("yes_bid_dollars"),
            "NO": m.get("no_bid_dollars"),
            "Volumen 24h": m.get("volume_24h_fp", 0),
            "Open Interest": m.get("open_interest_fp", 0),
            "Horas": hours
        })

    return pd.DataFrame(rows)


def format_table(df):

    if df.empty:
        return df

    result = df.copy()

    result["YES"] = result["YES"].apply(
        lambda x: f"{float(x):.2f}"
        if pd.notna(x) else "—"
    )

    result["NO"] = result["NO"].apply(
        lambda x: f"{float(x):.2f}"
        if pd.notna(x) else "—"
    )

    result["Volumen 24h"] = result["Volumen 24h"].apply(
        lambda x: f"{float(x):,.0f}"
    )

    result["Open Interest"] = result["Open Interest"].apply(
        lambda x: f"{float(x):,.0f}"
    )

    result["Horas"] = result["Horas"].apply(
        lambda x: f"{x:.1f} h"
    )

    return result


# --------------------------------------------------
# INTERFAZ
# --------------------------------------------------

if st.button("🔄 REFRESH", use_container_width=True):

    with st.spinner("Consultando Kalshi..."):

        try:

            markets = get_markets()

            df = prepare_data(markets)

            if df.empty:

                st.warning(
                    "No encontramos mercados que cumplan "
                    "los filtros actuales."
                )

            else:

                st.success(
                    f"{len(df)} mercados encontrados."
                )

                for cat in [
                    "Economía",
                    "Finanzas",
                    "Deportes"
                ]:

                    st.subheader(
                        f"{'📈' if cat == 'Economía' else '💰' if cat == 'Finanzas' else '🏆'} {cat}"
                    )

                    section = df[
                        df["Categoría"] == cat
                    ].copy()

                    section = section.sort_values(
                        "Volumen 24h",
                        ascending=False
                    ).head(10)

                    section = section.drop(
                        columns=["Categoría"]
                    )

                    section.insert(
                        0,
                        "#",
                        range(1, len(section) + 1)
                    )

                    section = format_table(section)

                    st.dataframe(
                        section,
                        use_container_width=True,
                        hide_index=True
                    )

        except Exception as e:

            st.error(
                f"No fue posible obtener los datos: {e}"
            )

else:

    st.info(
        "Pulsa 🔄 REFRESH para cargar los mercados."
    )

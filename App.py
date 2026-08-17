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
            API_URL,
            params=params,
            timeout=30
        )

        response.raise_for_status()

        data = response.json()

        markets.extend(
            data.get("markets", [])
        )

        cursor = data.get("cursor")

        if not cursor:
            break

    return markets


# ============================================================
# HORAS HASTA EL VENCIMIENTO
# ============================================================

def hours_to_close(close_time):

    try:

        close = datetime.fromisoformat(
            close_time.replace("Z", "+00:00")
        )

        now = datetime.now(timezone.utc)

        return (
            close - now
        ).total_seconds() / 3600

    except:

        return None


# ============================================================
# CLASIFICACIÓN PROVISIONAL
# ============================================================

def get_category(market):

    text = (
        str(market.get("title", "")) +
        " " +
        str(market.get("subtitle", "")) +
        " " +
        str(market.get("ticker", ""))
    ).lower()

    # -----------------------------
    # DEPORTES
    # -----------------------------

    sports_words = [
        "nfl",
        "nba",
        "wnba",
        "nhl",
        "mlb",
        "soccer",
        "football",
        "baseball",
        "basketball",
        "hockey",
        "tennis",
        "golf",
        "ufc",
        "boxing",
        "match",
        "game",
        "team",
        "league",
        "championship"
    ]

    # -----------------------------
    # FINANZAS
    # -----------------------------

    finance_words = [
        "bitcoin",
        "btc",
        "ethereum",
        "eth",
        "crypto",
        "stock",
        "stocks",
        "nasdaq",
        "s&p",
        "sp500",
        "dow",
        "earnings",
        "gold",
        "silver",
        "oil",
        "finance",
        "financial",
        "market"
    ]

    # -----------------------------
    # ECONOMÍA
    # -----------------------------

    economy_words = [
        "fed",
        "federal reserve",
        "inflation",
        "cpi",
        "gdp",
        "jobs",
        "employment",
        "unemployment",
        "interest rate",
        "interest rates",
        "recession",
        "economy",
        "economic",
        "tariff",
        "treasury"
    ]

    if any(
        word in text
        for word in sports_words
    ):
        return "Deportes"

    if any(
        word in text
        for word in finance_words
    ):
        return "Finanzas"

    if any(
        word in text
        for word in economy_words
    ):
        return "Economía"

    return None


# ============================================================
# PREPARAR DATOS
# ============================================================

def prepare_data(markets):

    rows = []

    for market in markets:

        # --------------------------------
        # STATUS
        # --------------------------------

        status = market.get("status")

        if status not in [
            "open",
            "active"
        ]:
            continue

        # --------------------------------
        # VENCIMIENTO
        # --------------------------------

        hours = hours_to_close(
            market.get(
                "close_time",
                ""
            )
        )

        if hours is None:
            continue

        # Solo mercados que vencen
        # entre 24 y 48 horas

        if hours < 24:
            continue

        if hours > 48:
            continue

        # --------------------------------
        # CATEGORÍA
        # --------------------------------

        category = get_category(
            market
        )

        if category is None:
            continue

        # --------------------------------
        # DATOS
        # --------------------------------

        title = (
            market.get("title")
            or market.get("subtitle")
            or market.get("ticker")
            or "Sin nombre"
        )

        yes_bid = market.get(
            "yes_bid_dollars"
        )

        yes_ask = market.get(
            "yes_ask_dollars"
        )

        no_bid = market.get(
            "no_bid_dollars"
        )

        no_ask = market.get(
            "no_ask_dollars"
        )

        volume = market.get(
            "volume_24h_fp",
            0
        )

        open_interest = market.get(
            "open_interest_fp",
            0
        )

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

    # --------------------------------
    # PRECIOS
    # --------------------------------

    price_columns = [
        "YES Bid",
        "YES Ask",
        "NO Bid",
        "NO Ask"
    ]

    for column in price_columns:

        result[column] = result[column].apply(

            lambda x:
                f"{float(x):.2f}"
                if pd.notna(x)
                else "—"

        )

    # --------------------------------
    # VOLUMEN
    # --------------------------------

    result["Volumen 24h"] = (
        result["Volumen 24h"]
        .apply(
            lambda x:
                f"{float(x):,.0f}"
        )
    )

    # --------------------------------
    # OPEN INTEREST
    # --------------------------------

    result["Open Interest"] = (
        result["Open Interest"]
        .apply(
            lambda x:
                f"{float(x):,.0f}"
        )
    )

    # --------------------------------
    # HORAS
    # --------------------------------

    result["Horas"] = (
        result["Horas"]
        .apply(
            lambda x:
                f"{x:.1f} h"
        )
    )

    return result


# ============================================================
# INTERFAZ
# ============================================================

st.title(
    "📊 Kalshi Trending Markets"
)

st.caption(
    "Top mercados por volumen · "
    "Vencimiento entre 24 y 48 horas"
)

# ============================================================
# BOTÓN REFRESH
# ============================================================

if st.button(
    "🔄 REFRESH",
    use_container_width=True
):

    with st.spinner(
        "Consultando mercados de Kalshi..."
    ):

        try:

            # --------------------------------
            # DESCARGAR
            # --------------------------------

            markets = get_markets()

            # --------------------------------
            # PROCESAR
            # --------------------------------

            df = prepare_data(
                markets
            )

            # --------------------------------
            # RESULTADO
            # --------------------------------

            if df.empty:

                st.warning(
                    "No encontramos mercados "
                    "que cumplan las condiciones."
                )

            else:

                st.success(
                    f"{len(df)} mercados "
                    f"encontrados."
                )

                # =================================================
                # ECONOMÍA
                # =================================================

                economy = df[
                    df["Categoría"]
                    == "Economía"
                ].copy()

                economy = economy.sort_values(
                    "Volumen 24h",
                    ascending=False
                ).head(10)

                if not economy.empty:

                    st.subheader(
                        "📈 Economía — Top 10"
                    )

                    economy = economy.drop(
                        columns=["Categoría"]
                    )

                    economy.insert(
                        0,
                        "#",
                        range(
                            1,
                            len(economy) + 1
                        )
                    )

                    economy = format_table(
                        economy
                    )

                    st.dataframe(
                        economy,
                        use_container_width=True,
                        hide_index=True
                    )

                # =================================================
                # FINANZAS
                # =================================================

                finance = df[
                    df["Categoría"]
                    == "Finanzas"
                ].copy()

                finance = finance.sort_values(
                    "Volumen 24h",
                    ascending=False
                ).head(10)

                if not finance.empty:

                    st.subheader(
                        "💰 Finanzas — Top 10"
                    )

                    finance = finance.drop(
                        columns=["Categoría"]
                    )

                    finance.insert(
                        0,
                        "#",
                        range(
                            1,
                            len(finance) + 1
                        )
                    )

                    finance = format_table(
                        finance
                    )

                    st.dataframe(
                        finance,
                        use_container_width=True,
                        hide_index=True
                    )

                # =================================================
                # DEPORTES
                # =================================================

                sports = df[
                    df["Categoría"]
                    == "Deportes"
                ].copy()

                sports = sports.sort_values(
                    "Volumen 24h",
                    ascending=False
                ).head(10)

                if not sports.empty:

                    st.subheader(
                        "🏆 Deportes — Top 10"
                    )

                    sports = sports.drop(
                        columns=["Categoría"]
                    )

                    sports.insert(
                        0,
                        "#",
                        range(
                            1,
                            len(sports) + 1
                        )
                    )

                    sports = format_table(
                        sports
                    )

                    st.dataframe(
                        sports,
                        use_container_width=True,
                        hide_index=True
                    )

        except Exception as error:

            st.error(
                "Error al consultar Kalshi:"
            )

            st.exception(
                error
            )

else:

    st.info(
        "Pulsa 🔄 REFRESH para cargar "
        "los mercados actuales."
    )

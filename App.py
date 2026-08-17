import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timezone

# ============================================================
# CONFIGURACIÓN
# ============================================================

st.set_page_config(
    page_title="Kalshi Trending",
    page_icon="📊",
    layout="wide"
)

API_URL = "https://api.elections.kalshi.com/trade-api/v2/markets"

MAX_HOURS = 25
TOP_N = 10


# ============================================================
# ESTILO
# ============================================================

st.markdown("""
<style>

.block-container {
    padding-top: 2rem;
    padding-bottom: 2rem;
}

.main-title {
    font-size: 34px;
    font-weight: 800;
    margin-bottom: 0px;
}

.subtitle {
    color: #6b7280;
    font-size: 15px;
    margin-bottom: 20px;
}

.category-title {
    font-size: 24px;
    font-weight: 800;
    margin-top: 25px;
    margin-bottom: 8px;
}

.info-box {
    padding: 12px 16px;
    border-radius: 10px;
    background: #f3f4f6;
    margin-bottom: 15px;
}

</style>
""", unsafe_allow_html=True)


# ============================================================
# ENCABEZADO
# ============================================================

st.markdown(
    '<div class="main-title">📊 Kalshi Trending Markets</div>',
    unsafe_allow_html=True
)

st.markdown(
    f'<div class="subtitle">'
    f'Top {TOP_N} mercados por categoría · '
    f'Vencimiento en menos de {MAX_HOURS} horas'
    f'</div>',
    unsafe_allow_html=True
)


# ============================================================
# CONVERSIÓN NUMÉRICA
# ============================================================

def to_number(value):

    if value is None:
        return None

    try:

        if isinstance(value, str):
            value = value.replace(",", "").strip()

        return float(value)

    except Exception:

        return None


# ============================================================
# FECHA
# ============================================================

def parse_datetime(value):

    if not value:
        return None

    try:

        return datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )

    except Exception:

        return None


# ============================================================
# DESCARGAR MERCADOS
# ============================================================

def fetch_markets():

    markets = []
    cursor = None

    for _ in range(20):

        params = {
            "limit": 1000,
            "status": "open"
        }

        if cursor:
            params["cursor"] = cursor

        try:

            response = requests.get(
                API_URL,
                params=params,
                timeout=30
            )

            response.raise_for_status()

            data = response.json()

        except requests.exceptions.RequestException as e:

            raise RuntimeError(
                f"No se pudo conectar con Kalshi: {e}"
            )

        except Exception as e:

            raise RuntimeError(
                f"Error procesando la respuesta: {e}"
            )

        batch = data.get("markets", [])

        if not batch:
            break

        markets.extend(batch)

        cursor = data.get("cursor")

        if not cursor:
            break

    return markets


# ============================================================
# CLASIFICACIÓN
# ============================================================

def classify_market(market):

    text = " ".join([
        str(market.get("title", "")),
        str(market.get("subtitle", "")),
        str(market.get("ticker", "")),
        str(market.get("event_ticker", ""))
    ]).lower()

    # --------------------------------------------------------
    # DEPORTES
    # --------------------------------------------------------

    sports = [

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
        "games",
        "team",

        "league",
        "championship",

        "doosan",
        "hanwha",
        "lotte",
        "samsung lions",
        "fukuoka hawks",
        "yomiuri",
        "rakuten",
        "chunichi",
        "orix",
        "hanshin",

        "barcelona",
        "psg",
        "juventus",
        "milan",
        "atletico",
        "wrexham",

        "ravens",
        "lions",

        "points scored",
        "goals scored",

        "player",
        "players"
    ]

    # --------------------------------------------------------
    # FINANZAS
    # --------------------------------------------------------

    finance = [

        "bitcoin",
        "btc",
        "ethereum",
        "eth",
        "crypto",
        "cryptocurrency",

        "stock",
        "stocks",
        "share",
        "shares",

        "nasdaq",
        "s&p",
        "sp500",
        "s&p 500",
        "dow",

        "earnings",
        "revenue",

        "gold",
        "silver",
        "copper",

        "oil",
        "crude",
        "gas",

        "market",
        "markets",

        "financial",
        "finance",

        "etf",

        "treasury",
        "bond",
        "bonds",

        "yield"
    ]

    # --------------------------------------------------------
    # ECONOMÍA
    # --------------------------------------------------------

    economy = [

        "fed",
        "federal reserve",

        "inflation",
        "cpi",
        "ppi",

        "gdp",
        "gross domestic product",

        "jobs",
        "job",
        "employment",
        "unemployment",

        "interest rate",
        "interest rates",

        "rate cut",
        "rate hike",

        "recession",

        "economy",
        "economic",

        "tariff",
        "tariffs",

        "consumer price",

        "nonfarm payroll",

        "fomc"
    ]

    # --------------------------------------------------------
    # PRIORIDAD
    # --------------------------------------------------------

    if any(word in text for word in sports):
        return "Deportes"

    if any(word in text for word in finance):
        return "Finanzas"

    if any(word in text for word in economy):
        return "Economía"

    return None


# ============================================================
# PROCESAR MERCADOS
# ============================================================

def process_markets(markets):

    now = datetime.now(timezone.utc)

    rows = []

    for market in markets:

        status = str(
            market.get("status", "")
        ).lower()

        if status not in [
            "open",
            "active"
        ]:
            continue

        # ----------------------------------------------------
        # VENCIMIENTO
        # ----------------------------------------------------

        close_time = (
            market.get("close_time")
            or market.get("expiration_time")
            or market.get("expected_expiration_time")
        )

        close_dt = parse_datetime(close_time)

        if close_dt is None:
            continue

        hours_left = (
            close_dt - now
        ).total_seconds() / 3600

        if hours_left <= 0:
            continue

        if hours_left >= MAX_HOURS:
            continue

        # ----------------------------------------------------
        # CATEGORÍA
        # ----------------------------------------------------

        category = classify_market(market)

        if category is None:
            continue

        # ----------------------------------------------------
        # NOMBRE
        # ----------------------------------------------------

        title = (
            market.get("title")
            or market.get("subtitle")
            or market.get("ticker")
            or "Sin título"
        )

        ticker = market.get(
            "ticker",
            ""
        )

        # ----------------------------------------------------
        # YES BID
        # ----------------------------------------------------

        yes_bid = to_number(
            market.get("yes_bid_dollars")
        )

        # ----------------------------------------------------
        # NO BID
        # ----------------------------------------------------

        no_bid = to_number(
            market.get("no_bid_dollars")
        )

        # ----------------------------------------------------
        # VOLUMEN
        # ----------------------------------------------------

        volume = market.get(
            "volume_24h_fp"
        )

        if volume is None:

            volume = market.get(
                "volume_24h",
                0
            )

        volume = to_number(volume)

        if volume is None:
            volume = 0

        # ----------------------------------------------------
        # FILA
        # ----------------------------------------------------

        rows.append({

            "Categoría": category,

            "Mercado": str(title),

            "Símbolo": str(ticker),

            "Vencimiento": close_dt,

            "Horas": hours_left,

            "YES Bid": yes_bid,

            "NO Bid": no_bid,

            "Volumen": volume
        })

    return pd.DataFrame(rows)


# ============================================================
# BOTÓN ACTUALIZAR
# ============================================================

if st.button(
    "🔄 ACTUALIZAR DATOS",
    type="primary",
    use_container_width=True
):

    st.cache_data.clear()
    st.rerun()


# ============================================================
# CARGAR DATOS
# ============================================================

with st.spinner(
    "🔎 Buscando mercados de Kalshi..."
):

    try:

        raw_markets = fetch_markets()

        df = process_markets(
            raw_markets
        )

    except Exception as error:

        st.error(
            "❌ Error al consultar Kalshi"
        )

        st.exception(error)

        st.stop()


# ============================================================
# SIN RESULTADOS
# ============================================================

if df.empty:

    st.warning(
        f"No encontramos mercados que venzan "
        f"en menos de {MAX_HOURS} horas."
    )

    st.info(
        f"Kalshi devolvió "
        f"{len(raw_markets):,} mercados."
    )

    st.stop()


# ============================================================
# FUNCIÓN PARA MOSTRAR TABLA
# ============================================================

def show_category(
    dataframe,
    category,
    icon
):

    section = dataframe[
        dataframe["Categoría"] == category
    ].copy()

    if section.empty:

        st.markdown(
            f"### {icon} {category}"
        )

        st.info(
            "No hay mercados disponibles "
            "en esta categoría."
        )

        return

    # --------------------------------------------------------
    # ORDENAR POR VOLUMEN
    # --------------------------------------------------------

    section = section.sort_values(
        "Volumen",
        ascending=False
    ).head(TOP_N)

    # --------------------------------------------------------
    # COPIA PARA PRESENTACIÓN
    # --------------------------------------------------------

    display = section.copy()

    # --------------------------------------------------------
    # NÚMERO
    # --------------------------------------------------------

    display.insert(
        0,
        "#",
        range(
            1,
            len(display) + 1
        )
    )

    # --------------------------------------------------------
    # VENCIMIENTO
    # --------------------------------------------------------

    display["Vencimiento"] = display[
        "Vencimiento"
    ].apply(

        lambda x:
        x.strftime("%d %b · %H:%M")

        if pd.notna(x)

        else "—"
    )

    # --------------------------------------------------------
    # YES BID
    # --------------------------------------------------------

    display["YES Bid"] = display[
        "YES Bid"
    ].apply(

        lambda x:
        f"{float(x):.2f}"

        if pd.notna(x)

        else "—"
    )

    # --------------------------------------------------------
    # NO BID
    # --------------------------------------------------------

    display["NO Bid"] = display[
        "NO Bid"
    ].apply(

        lambda x:
        f"{float(x):.2f}"

        if pd.notna(x)

        else "—"
    )

    # --------------------------------------------------------
    # HORAS
    # --------------------------------------------------------

    display["Horas"] = display[
        "Horas"
    ].apply(

        lambda x:
        f"{float(x):.1f} h"
    )

    # --------------------------------------------------------
    # COLUMNAS FINALES
    # --------------------------------------------------------

    display = display[
        [
            "#",
            "Mercado",
            "Vencimiento",
            "Horas",
            "YES Bid",
            "NO Bid"
        ]
    ]

    # --------------------------------------------------------
    # TÍTULO
    # --------------------------------------------------------

    st.markdown(
        f'<div class="category-title">'
        f'{icon} {category}'
        f'</div>',
        unsafe_allow_html=True
    )

    st.caption(
        f"Top {len(display)} mercados · "
        f"ordenados por volumen 24h"
    )

    # --------------------------------------------------------
    # TABLA
    # --------------------------------------------------------

    st.dataframe(

        display,

        use_container_width=True,

        hide_index=True,

        column_config={

            "#": st.column_config.NumberColumn(
                "#",
                width="small"
            ),

            "Mercado": st.column_config.TextColumn(
                "Mercado / Evento",
                width="large"
            ),

            "Vencimiento": st.column_config.TextColumn(
                "Vencimiento",
                width="medium"
            ),

            "Horas": st.column_config.TextColumn(
                "Tiempo restante",
                width="small"
            ),

            "YES Bid": st.column_config.TextColumn(
                "YES Bid",
                width="small"
            ),

            "NO Bid": st.column_config.TextColumn(
                "NO Bid",
                width="small"
            )
        }
    )

    st.markdown("---")


# ============================================================
# TABLAS
# ============================================================

show_category(
    df,
    "Economía",
    "📈"
)

show_category(
    df,
    "Finanzas",
    "💰"
)

show_category(
    df,
    "Deportes",
    "🏆"
)


# ============================================================
# PIE
# ============================================================

st.caption(
    f"Actualizado: "
    f"{datetime.now().strftime('%d/%m/%Y %H:%M:%S')} · "
    f"Universo analizado: {len(raw_markets):,} mercados"
)

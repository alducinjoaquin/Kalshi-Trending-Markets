import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timezone

# ============================================================
# CONFIGURACIÓN
# ============================================================

st.set_page_config(
    page_title="Kalshi < 25h",
    page_icon="📊",
    layout="wide"
)

API_URL = "https://api.elections.kalshi.com/trade-api/v2/markets"

LIMIT = 10
MAX_HOURS = 25


# ============================================================
# TÍTULO
# ============================================================

st.title(
    f"📊 Kalshi — Top {LIMIT} contratos que vencen en < {MAX_HOURS} horas"
)

st.caption(
    "Ordenados por volumen de las últimas 24 horas"
)


# ============================================================
# OBTENER MERCADOS
# ============================================================

def fetch_markets():

    markets = []
    cursor = None

    for page in range(20):

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
                f"Error conectando con Kalshi: {e}"
            )

        except Exception as e:

            raise RuntimeError(
                f"Error procesando respuesta de Kalshi: {e}"
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
# CONVERTIR FECHA
# ============================================================

def parse_datetime(value):

    if not value:
        return None

    try:

        return datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )

    except Exception:

        return None


# ============================================================
# PROCESAR MERCADOS
# ============================================================

def process_markets(markets):

    now = datetime.now(timezone.utc)

    rows = []

    for m in markets:

        # ----------------------------------------------------
        # FECHA DE CIERRE
        # ----------------------------------------------------

        close_time = (
            m.get("close_time")
            or m.get("expiration_time")
            or m.get("expected_expiration_time")
        )

        close_dt = parse_datetime(close_time)

        if close_dt is None:
            continue

        hours_left = (
            close_dt - now
        ).total_seconds() / 3600

        # ----------------------------------------------------
        # FILTRO < 25 HORAS
        # ----------------------------------------------------

        if hours_left <= 0:
            continue

        if hours_left >= MAX_HOURS:
            continue

        # ----------------------------------------------------
        # PRECIOS REALES DE KALSHI
        # ----------------------------------------------------

        yes_bid = m.get("yes_bid_dollars")
        yes_ask = m.get("yes_ask_dollars")

        no_bid = m.get("no_bid_dollars")
        no_ask = m.get("no_ask_dollars")

        # ----------------------------------------------------
        # VOLUMEN
        # ----------------------------------------------------

        volume_24h = (
            m.get("volume_24h_fp")
            or m.get("volume_24h")
            or 0
        )

        open_interest = (
            m.get("open_interest_fp")
            or m.get("open_interest")
            or 0
        )

        # ----------------------------------------------------
        # NOMBRE
        # ----------------------------------------------------

        title = (
            m.get("title")
            or m.get("subtitle")
            or m.get("ticker")
            or "Sin título"
        )

        ticker = m.get(
            "ticker",
            ""
        )

        # ----------------------------------------------------
        # FILA
        # ----------------------------------------------------

        rows.append({

            "Mercado": title,

            "Símbolo": ticker,

            "Vencimiento": close_dt.strftime(
                "%d/%m %H:%M"
            ),

            "Horas": hours_left,

            "YES Bid": yes_bid,

            "YES Ask": yes_ask,

            "NO Bid": no_bid,

            "NO Ask": no_ask,

            "Vol. 24h": volume_24h,

            "Open Interest": open_interest
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
# EJECUCIÓN
# ============================================================

with st.spinner(
    f"Buscando mercados que vencen en menos de {MAX_HOURS} horas..."
):

    try:

        raw_markets = fetch_markets()

        df = process_markets(
            raw_markets
        )

    except Exception as e:

        st.error(
            "No fue posible obtener los datos de Kalshi."
        )

        st.exception(e)

        st.stop()


# ============================================================
# RESULTADOS
# ============================================================

if df.empty:

    st.warning(
        f"Kalshi no devolvió mercados que cumplan "
        f"el filtro de menos de {MAX_HOURS} horas."
    )

    st.info(
        f"Mercados recibidos desde Kalshi: "
        f"{len(raw_markets)}"
    )

else:

    # --------------------------------------------------------
    # ORDENAR POR VOLUMEN
    # --------------------------------------------------------

    df = df.sort_values(
        "Vol. 24h",
        ascending=False
    )

    df = df.head(LIMIT)

    # --------------------------------------------------------
    # MÉTRICAS
    # --------------------------------------------------------

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Mercados encontrados",
        len(df)
    )

    col2.metric(
        "Mayor volumen 24h",
        f"{df['Vol. 24h'].max():,.0f}"
    )

    col3.metric(
        "Vencimiento más próximo",
        f"{df['Horas'].min():.1f} h"
    )

    st.divider()

    # --------------------------------------------------------
    # FORMATO
    # --------------------------------------------------------

    display = df.copy()

    for col in [
        "YES Bid",
        "YES Ask",
        "NO Bid",
        "NO Ask"
    ]:

        display[col] = display[col].apply(
            lambda x:
            f"{float(x):.2f}"
            if pd.notna(x)
            else "—"
        )

    display["Vol. 24h"] = display[
        "Vol. 24h"
    ].apply(
        lambda x:
        f"{float(x):,.0f}"
    )

    display["Open Interest"] = display[
        "Open Interest"
    ].apply(
        lambda x:
        f"{float(x):,.0f}"
    )

    display["Horas"] = display[
        "Horas"
    ].apply(
        lambda x:
        f"{x:.1f} h"
    )

    display.insert(
        0,
        "#",
        range(
            1,
            len(display) + 1
        )
    )

    # --------------------------------------------------------
    # TABLA
    # --------------------------------------------------------

    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True,
        column_config={

            "Mercado": st.column_config.TextColumn(
                "Mercado",
                width="large"
            ),

            "Símbolo": st.column_config.TextColumn(
                "Símbolo",
                width="medium"
            ),

            "YES Bid": st.column_config.TextColumn(
                "YES Bid",
                width="small"
            ),

            "YES Ask": st.column_config.TextColumn(
                "YES Ask",
                width="small"
            ),

            "NO Bid": st.column_config.TextColumn(
                "NO Bid",
                width="small"
            ),

            "NO Ask": st.column_config.TextColumn(
                "NO Ask",
                width="small"
            ),

            "Vol. 24h": st.column_config.TextColumn(
                "Vol. 24h",
                width="medium"
            ),

            "Open Interest": st.column_config.TextColumn(
                "Open Interest",
                width="medium"
            ),

            "Horas": st.column_config.TextColumn(
                "Vence",
                width="small"
            )
        }
    )

    st.caption(
        f"Actualizado: "
        f"{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
    )

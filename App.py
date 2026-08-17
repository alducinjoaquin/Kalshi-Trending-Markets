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

MAX_HOURS = 25
TOP_N = 10


# ============================================================
# ESTILO VISUAL
# ============================================================

st.markdown("""
<style>

.main-title {
    font-size: 32px;
    font-weight: 700;
    margin-bottom: 0;
}

.subtitle {
    color: #6b7280;
    font-size: 14px;
    margin-bottom: 20px;
}

.metric-card {
    padding: 15px;
    border-radius: 12px;
    background-color: #f5f7fa;
    text-align: center;
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
    f'Mercados que vencen en menos de {MAX_HOURS} horas · '
    f'ordenados por volumen'
    f'</div>',
    unsafe_allow_html=True
)


# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

def to_number(value, default=0.0):

    if value is None:
        return default

    try:

        if isinstance(value, str):

            value = value.replace(",", "").strip()

            if value == "":
                return default

        return float(value)

    except Exception:

        return default


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

@st.cache_data(ttl=60)
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

        except requests.exceptions.RequestException as error:

            raise RuntimeError(
                f"Error de conexión con Kalshi: {error}"
            )

        except Exception as error:

            raise RuntimeError(
                f"Error procesando la respuesta de Kalshi: {error}"
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
# PROCESAR MERCADOS
# ============================================================

def process_markets(markets):

    now = datetime.now(timezone.utc)

    rows = []

    for market in markets:

        # ----------------------------------------------------
        # STATUS
        # ----------------------------------------------------

        status = str(
            market.get("status", "")
        ).lower()

        if status not in [
            "open",
            "active"
        ]:
            continue

        # ----------------------------------------------------
        # FECHA DE CIERRE
        # ----------------------------------------------------

        close_time = (
            market.get("close_time")
            or market.get("expiration_time")
            or market.get("expected_expiration_time")
        )

        close_dt = parse_datetime(
            close_time
        )

        if close_dt is None:
            continue

        # ----------------------------------------------------
        # HORAS RESTANTES
        # ----------------------------------------------------

        hours_left = (
            close_dt - now
        ).total_seconds() / 3600

        if hours_left <= 0:
            continue

        if hours_left >= MAX_HOURS:
            continue

        # ----------------------------------------------------
        # DATOS DE MERCADO
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
        # PRECIOS
        # ----------------------------------------------------

        yes_bid = to_number(
            market.get("yes_bid_dollars"),
            None
        )

        yes_ask = to_number(
            market.get("yes_ask_dollars"),
            None
        )

        no_bid = to_number(
            market.get("no_bid_dollars"),
            None
        )

        no_ask = to_number(
            market.get("no_ask_dollars"),
            None
        )

        # ----------------------------------------------------
        # VOLUMEN
        # ----------------------------------------------------

        volume_raw = (
            market.get("volume_24h_fp")
            if market.get("volume_24h_fp") is not None
            else market.get("volume_24h")
        )

        volume_24h = to_number(
            volume_raw,
            0
        )

        # ----------------------------------------------------
        # OPEN INTEREST
        # ----------------------------------------------------

        oi_raw = (
            market.get("open_interest_fp")
            if market.get("open_interest_fp") is not None
            else market.get("open_interest")
        )

        open_interest = to_number(
            oi_raw,
            0
        )

        # ----------------------------------------------------
        # GUARDAR
        # ----------------------------------------------------

        rows.append({

            "Mercado": str(title),

            "Símbolo": str(ticker),

            "Vencimiento": close_dt,

            "Horas": float(hours_left),

            "YES Bid": yes_bid,

            "YES Ask": yes_ask,

            "NO Bid": no_bid,

            "NO Ask": no_ask,

            "Volumen 24h": float(volume_24h),

            "Open Interest": float(open_interest)

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
# OBTENER DATOS
# ============================================================

with st.spinner(
    f"Consultando Kalshi y buscando mercados "
    f"que vencen en menos de {MAX_HOURS} horas..."
):

    try:

        raw_markets = fetch_markets()

        df = process_markets(
            raw_markets
        )

    except Exception as error:

        st.error(
            "No fue posible obtener los datos de Kalshi."
        )

        st.exception(error)

        st.stop()


# ============================================================
# SIN RESULTADOS
# ============================================================

if df.empty:

    st.warning(
        f"No encontramos mercados con vencimiento "
        f"en menos de {MAX_HOURS} horas."
    )

    st.info(
        f"Mercados descargados desde Kalshi: "
        f"{len(raw_markets)}"
    )

    st.stop()


# ============================================================
# ORDENAR
# ============================================================

df = df.sort_values(
    "Volumen 24h",
    ascending=False
).head(TOP_N)


# ============================================================
# MÉTRICAS
# ============================================================

max_volume = float(
    df["Volumen 24h"]
    .fillna(0)
    .max()
)

min_hours = float(
    df["Horas"]
    .fillna(0)
    .min()
)

total_volume = float(
    df["Volumen 24h"]
    .fillna(0)
    .sum()
)


col1, col2, col3 = st.columns(3)

with col1:

    st.metric(
        "Mercados",
        len(df)
    )

with col2:

    st.metric(
        "Mayor volumen 24h",
        f"{max_volume:,.0f}"
    )

with col3:

    st.metric(
        "Próximo vencimiento",
        f"{min_hours:.1f} h"
    )


st.divider()


# ============================================================
# PREPARAR TABLA
# ============================================================

display = df.copy()

display.insert(
    0,
    "#",
    range(
        1,
        len(display) + 1
    )
)


# ------------------------------------------------------------
# FORMATO DE PRECIOS
# ------------------------------------------------------------

def format_price(value):

    if pd.isna(value):

        return "—"

    try:

        return f"{float(value):.2f}"

    except:

        return "—"


for column in [
    "YES Bid",
    "YES Ask",
    "NO Bid",
    "NO Ask"
]:

    display[column] = display[
        column
    ].apply(format_price)


# ------------------------------------------------------------
# FORMATO VOLUMEN
# ------------------------------------------------------------

display["Volumen 24h"] = display[
    "Volumen 24h"
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


# ------------------------------------------------------------
# FORMATO HORAS
# ------------------------------------------------------------

display["Horas"] = display[
    "Horas"
].apply(
    lambda x:
    f"{float(x):.1f} h"
)


# ------------------------------------------------------------
# FORMATO FECHA
# ------------------------------------------------------------

display["Vencimiento"] = display[
    "Vencimiento"
].apply(
    lambda x:
    x.strftime("%d/%m %H:%M")
    if pd.notna(x)
    else "—"
)


# ============================================================
# TABLA
# ============================================================

st.subheader(
    "🔥 Top mercados por volumen"
)

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
            "Mercado",
            width="large"
        ),

        "Símbolo": st.column_config.TextColumn(
            "Símbolo",
            width="medium"
        ),

        "Vencimiento": st.column_config.TextColumn(
            "Vencimiento",
            width="medium"
        ),

        "Horas": st.column_config.TextColumn(
            "Tiempo",
            width="small"
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

        "Volumen 24h": st.column_config.TextColumn(
            "Vol. 24h",
            width="medium"
        ),

        "Open Interest": st.column_config.TextColumn(
            "Open Interest",
            width="medium"
        )
    }
)


# ============================================================
# INFORMACIÓN
# ============================================================

st.caption(
    f"Última actualización: "
    f"{datetime.now().strftime('%d/%m/%Y %H:%M:%S')} · "
    f"Se analizaron {len(raw_markets):,} mercados recibidos de Kalshi."
)

import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timezone, timedelta

# ============================================================
# CONFIGURACIÓN
# ============================================================

st.set_page_config(
    page_title="Kalshi Trending Markets",
    page_icon="📊",
    layout="wide"
)

BASE_URL = "https://external-api.kalshi.com/trade-api/v2"

MAX_HOURS = 25
TOP_N = 10

# Series ticker de "ganador del partido" (moneyline) por liga.
# Confirmado contra la documentación pública de Kalshi.
SPORTS_SERIES = {
    "KXNFLGAME": "NFL",
    "KXNCAAFGAME": "NCAAF",
    "KXMLBGAME": "MLB",
    "KXNBAGAME": "NBA",
}


# ============================================================
# ESTILO
# ============================================================

st.markdown("""
<style>

.block-container {
    padding-top: 1.5rem;
    padding-left: 2rem;
    padding-right: 2rem;
}

.main-title {
    font-size: 34px;
    font-weight: 800;
    margin-bottom: 0;
}

.subtitle {
    color: #6b7280;
    font-size: 15px;
    margin-bottom: 20px;
}

.section {
    font-size: 25px;
    font-weight: 800;
    margin-top: 28px;
    margin-bottom: 4px;
}

.section-note {
    color: #6b7280;
    font-size: 13px;
    margin-bottom: 10px;
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
    f'Top {TOP_N} mercados · vencimiento en menos de '
    f'{MAX_HOURS} horas · ordenados por interés abierto '
    f'(desempate por volumen 24h)'
    f'</div>',
    unsafe_allow_html=True
)


# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

def get_number(value):
    """Convierte valores de Kalshi (strings de punto fijo) a float."""

    if value is None:
        return 0.0

    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def parse_time(value):
    """Convierte timestamp ISO de Kalshi a datetime UTC."""

    if not value:
        return None

    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt

    except (TypeError, ValueError):
        return None


def format_pct(value):
    """Convierte un precio en dólares (0.0-1.0) a texto de porcentaje."""

    return f"{value * 100:.2f}%"


# ============================================================
# OBTENER EVENTOS (paginado, todas las categorías abiertas)
# ============================================================

@st.cache_data(ttl=60)
def get_events():

  
    events = []
    cursor = ""

    for _ in range(30):

        params = {
            "limit": 200,
            "with_nested_markets": "true",
            "status": "open",
        }

        if cursor:
            params["cursor"] = cursor

        response = requests.get(
            f"{BASE_URL}/events",
            params=params,
            timeout=30
        )

        response.raise_for_status()

        data = response.json()

        batch = data.get("events", [])

        if not batch:
            break

        events.extend(batch)

        cursor = data.get("cursor", "")

        if not cursor:
            break

    return events


# ============================================================
# PROCESAR EVENTOS
# ============================================================

def build_dataframe(events):

    now = datetime.now(timezone.utc)
    max_close = now + timedelta(hours=MAX_HOURS)

    rows = []

    for event in events:

        # ----------------------------------------------------
        # CLASIFICAR CATEGORÍA
        # ----------------------------------------------------

        series_ticker = str(event.get("series_ticker", "")).strip()
        category = str(event.get("category", "")).strip().lower()

        if series_ticker in SPORTS_SERIES:
            category_final = "Deportes"

        elif category in ["financials", "finance", "financial"]:
            category_final = "Finanzas"

        elif category in ["economics", "economy"]:
            category_final = "Economía"

        else:
            continue

        event_title = (
            event.get("title")
            or event.get("sub_title")
            or event.get("event_ticker")
            or "Sin título"
        )

        markets = event.get("markets", [])

        for market in markets:

            # ------------------------------------------------
            # STATUS DEL MERCADO
            # ------------------------------------------------

            status = str(market.get("status", "")).lower()

            if status != "open":
                continue

            # ------------------------------------------------
            # FECHA DE CIERRE / VENTANA 0-25H
            # ------------------------------------------------

            close_dt = parse_time(market.get("close_time"))

            if close_dt is None:
                continue

            if close_dt <= now or close_dt > max_close:
                continue

            # ------------------------------------------------
            # TÍTULO DEL MERCADO
            # ------------------------------------------------

            market_title = (
                market.get("title")
                or market.get("yes_sub_title")
                or market.get("subtitle")
                or event_title
            )

            market_title = str(market_title).strip()

            if not market_title:
                market_title = event_title

            # ------------------------------------------------
            # PRECIOS (dólares, 0.0-1.0) Y VOLUMEN / INTERÉS
            # ------------------------------------------------

            yes_bid = get_number(market.get("yes_bid_dollars"))
            no_bid = get_number(market.get("no_bid_dollars"))

            volume = get_number(market.get("volume_24h_fp"))
            open_interest = get_number(market.get("open_interest_fp"))

            rows.append({
                "Categoría": category_final,
                "Liga": SPORTS_SERIES.get(series_ticker, ""),
                "Mercado": market_title,
                "Vencimiento": close_dt,
                "YES Bid": yes_bid,
                "NO Bid": no_bid,
                "Volumen": volume,
                "Interés Abierto": open_interest,
                "Ticker": market.get("ticker", ""),
            })

    return pd.DataFrame(rows)


# ============================================================
# BOTÓN ACTUALIZAR
# ============================================================

if st.button("🔄 ACTUALIZAR DATOS", type="primary", use_container_width=True):
    st.cache_data.clear()
    st.rerun()


# ============================================================
# CONSULTA
# ============================================================


    with st.spinner("🔎 Consultando mercados de Kalshi..."):

    try:
        events = get_events()
        df = build_dataframe(events)

        st.write("Total eventos:", len(events))
        st.write("Categorías únicas:", sorted(set(str(e.get("category")) for e in events)))
        st.write("Series tickers únicos:", sorted(set(str(e.get("series_ticker")) for e in events))[:50])

    except requests.exceptions.RequestException as error:
        st.error("❌ Error de conexión con Kalshi.")
        st.code(str(error))
        st.stop()

    except Exception as error:
        st.error("❌ Error procesando los datos.")
        st.code(str(error))
        st.stop()

# ============================================================
# RESULTADO VACÍO
# ============================================================

if df.empty:

    st.warning(
        "No encontramos mercados de Economía, Finanzas o Deportes "
        f"(ganador del partido: NFL, NCAAF, MLB, NBA) que venzan en "
        f"menos de {MAX_HOURS} horas."
    )

    st.info(f"Eventos recibidos desde Kalshi: {len(events):,}")

    st.stop()


# ============================================================
# FUNCIÓN PARA MOSTRAR CATEGORÍA
# ============================================================

def show_category(dataframe, category, icon):

    data = dataframe[dataframe["Categoría"] == category].copy()

    # --------------------------------------------------------
    # ORDEN: PRIORIDAD A INTERÉS ABIERTO, DESEMPATE POR VOLUMEN
    # --------------------------------------------------------

    data = data.sort_values(
        ["Interés Abierto", "Volumen"],
        ascending=[False, False]
    ).head(TOP_N)

    st.markdown(
        f'<div class="section">{icon} {category}</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        f'<div class="section-note">'
        f'Top {len(data)} · ordenados por interés abierto '
        f'(desempate por volumen 24h)'
        f'</div>',
        unsafe_allow_html=True
    )

    if data.empty:
        st.info("No hay mercados disponibles en esta categoría.")
        return

    table = pd.DataFrame()

    table["Mercado / Evento"] = data["Mercado"]

    table["Vencimiento"] = data["Vencimiento"].apply(
        lambda x: x.strftime("%d %b · %H:%M")
    )

    table["YES Bid"] = data["YES Bid"].apply(format_pct)
    table["NO Bid"] = data["NO Bid"].apply(format_pct)

    st.dataframe(
        table,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Mercado / Evento": st.column_config.TextColumn(
                "Mercado / Evento", width="large"
            ),
            "Vencimiento": st.column_config.TextColumn(
                "Vencimiento", width="medium"
            ),
            "YES Bid": st.column_config.TextColumn(
                "YES Bid", width="small"
            ),
            "NO Bid": st.column_config.TextColumn(
                "NO Bid", width="small"
            ),
        }
    )

    st.markdown("---")


# ============================================================
# LAS 3 TABLAS
# ============================================================

show_category(df, "Economía", "📈")
show_category(df, "Finanzas", "💰")
show_category(df, "Deportes", "🏆")


# ============================================================
# PIE
# ============================================================

st.caption(
    "Fuente: Kalshi · "
    f"Actualizado {datetime.now().strftime('%d/%m/%Y %H:%M:%S')} · "
    f"Ventana: 0–{MAX_HOURS} horas · "
    "Deportes = ganador del partido (NFL, NCAAF, MLB, NBA)"
)

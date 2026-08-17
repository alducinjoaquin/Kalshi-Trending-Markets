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

# Series de "ganador del partido" (moneyline) por liga.
# Confirmado contra la documentación pública de Kalshi.
SPORTS_SERIES = {
    "KXNFLGAME": "NFL",
    "KXNCAAFGAME": "NCAAF",
    "KXMLBGAME": "MLB",
    "KXNBAGAME": "NBA",
}

# Categorías (a nivel de serie, que es la fuente de verdad actual;
# el campo "category" a nivel de evento está deprecado en la API).
FINANZAS_CATEGORIAS = {"financials", "finance", "financial"}
ECONOMIA_CATEGORIAS = {"economics", "economy"}


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
# PASO 1 — DESCUBRIR QUÉ SERIES PERTENECEN A CADA CATEGORÍA
# ============================================================

@st.cache_data(ttl=300)
def get_all_series():
    """Trae el catálogo completo de series (son cientos, no miles)."""

    response = requests.get(f"{BASE_URL}/series", timeout=30)
    response.raise_for_status()

    return response.json().get("series", [])


def get_target_series_tickers():
    """
    Devuelve un dict {series_ticker: categoria_final} solo para las
    series que nos interesan: Finanzas, Economía y las 4 ligas de
    Deportes. Evita tener que escanear todos los eventos abiertos.
    """

    targets = dict(SPORTS_SERIES)  # arranca con las 4 ligas

    for series in get_all_series():

        ticker = series.get("ticker", "")
        category = str(series.get("category", "")).strip().lower()

        if ticker in targets:
            continue  # ya está cubierto como serie deportiva

        if category in FINANZAS_CATEGORIAS:
            targets[ticker] = "Finanzas"

        elif category in ECONOMIA_CATEGORIAS:
            targets[ticker] = "Economía"

    return targets


# ============================================================
# PASO 2 — TRAER EVENTOS SOLO DE ESAS SERIES ESPECÍFICAS
# ============================================================

@st.cache_data(ttl=60)
def get_events_for_series(series_ticker):
    """Trae eventos abiertos de UNA serie puntual (paginado por si acaso)."""

    events = []
    cursor = ""

    for _ in range(10):

        params = {
            "series_ticker": series_ticker,
            "status": "open",
            "with_nested_markets": "true",
            "limit": 200,
        }

        if cursor:
            params["cursor"] = cursor

        response = requests.get(f"{BASE_URL}/events", params=params, timeout=30)
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
# PROCESAR EVENTOS → FILAS DE TABLA
# ============================================================

def build_dataframe(targets):

    now = datetime.now(timezone.utc)
    max_close = now + timedelta(hours=MAX_HOURS)

    rows = []
    total_events_fetched = 0

    for series_ticker, category_final in targets.items():

        events = get_events_for_series(series_ticker)
        total_events_fetched += len(events)

        for event in events:

            event_title = (
                event.get("title")
                or event.get("sub_title")
                or event.get("event_ticker")
                or "Sin título"
            )

            markets = event.get("markets", [])

            for market in markets:

                status = str(market.get("status", "")).lower()

                if status != "open":
                    continue

                close_dt = parse_time(market.get("close_time"))

                if close_dt is None:
                    continue

                if close_dt <= now or close_dt > max_close:
                    continue

                market_title = (
                    market.get("yes_sub_title")
                    or market.get("title")
                    or market.get("subtitle")
                    or event_title
                )

                market_title = str(market_title).strip() or event_title

                yes_bid = get_number(market.get("yes_bid_dollars"))
                no_bid = get_number(market.get("no_bid_dollars"))
                volume = get_number(market.get("volume_24h_fp"))
                open_interest = get_number(market.get("open_interest_fp"))

                rows.append({
                    "Categoría": category_final,
                    "Mercado": market_title,
                    "Vencimiento": close_dt,
                    "YES Bid": yes_bid,
                    "NO Bid": no_bid,
                    "Volumen": volume,
                    "Interés Abierto": open_interest,
                    "Ticker": market.get("ticker", ""),
                })

    return pd.DataFrame(rows), total_events_fetched


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
        targets = get_target_series_tickers()
        df, total_events_fetched = build_dataframe(targets)

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

    st.info(
        f"Series consultadas: {len(targets)} · "
        f"Eventos revisados en esas series: {total_events_fetched:,}"
    )

    st.stop()


# ============================================================
# FUNCIÓN PARA MOSTRAR CATEGORÍA
# ============================================================

def show_category(dataframe, category, icon):

    data = dataframe[dataframe["Categoría"] == category].copy()

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

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
    f'{MAX_HOURS} horas · ordenados por volumen 24h'
    f'</div>',
    unsafe_allow_html=True
)


# ============================================================
# FUNCIONES
# ============================================================

def get_number(value):
    """Convierte valores de Kalshi a float."""

    if value is None:
        return 0.0

    try:
        return float(value)
    except:
        return 0.0


def parse_time(value):
    """Convierte timestamp ISO de Kalshi a datetime UTC."""

    if not value:
        return None

    try:
        dt = datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )

        if dt.tzinfo is None:
            dt = dt.replace(
                tzinfo=timezone.utc
            )

        return dt

    except:
        return None


# ============================================================
# OBTENER EVENTOS CON MERCADOS
# ============================================================

@st.cache_data(ttl=60)
def get_events():

    now = datetime.now(timezone.utc)

    min_close_ts = int(
        now.timestamp()
    )

    events = []

    cursor = ""

    for _ in range(20):

        params = {
            "limit": 200,
            "with_nested_markets": "true",
            "status": "open",
            "min_close_ts": min_close_ts
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

        batch = data.get(
            "events",
            []
        )

        if not batch:
            break

        events.extend(batch)

        cursor = data.get(
            "cursor",
            ""
        )

        if not cursor:
            break

    return events


# ============================================================
# PROCESAR EVENTOS
# ============================================================

def build_dataframe(events):

    now = datetime.now(timezone.utc)

    max_close = (
        now +
        timedelta(hours=MAX_HOURS)
    )

    rows = []

    for event in events:

        # ----------------------------------------------------
        # CATEGORÍA REAL DE KALSHI
        # ----------------------------------------------------

        category = str(
            event.get(
                "category",
                ""
            )
        ).strip()

        # ----------------------------------------------------
        # SOLO NUESTRAS 3 CATEGORÍAS
        # ----------------------------------------------------

        category_lower = category.lower()

        if category_lower in [
            "sports",
            "sport"
        ]:

            category_final = "Deportes"

        elif category_lower in [
            "economics",
            "economy"
        ]:

            category_final = "Economía"

        elif category_lower in [
            "finance",
            "financial"
        ]:

            category_final = "Finanzas"

        else:

            continue

        # ----------------------------------------------------
        # TÍTULO DEL EVENTO
        # ----------------------------------------------------

        event_title = (
            event.get("title")
            or event.get("sub_title")
            or event.get("event_ticker")
            or "Sin título"
        )

        markets = event.get(
            "markets",
            []
        )

        for market in markets:

            # ------------------------------------------------
            # STATUS DEL MERCADO
            # ------------------------------------------------

            status = str(
                market.get(
                    "status",
                    ""
                )
            ).lower()

            if status != "open":
                continue

            # ------------------------------------------------
            # FECHA DE CIERRE
            # ------------------------------------------------

            close_dt = parse_time(
                market.get(
                    "close_time"
                )
            )

            if close_dt is None:
                continue

            # ------------------------------------------------
            # FILTRO 0 - 25 HORAS
            # ------------------------------------------------

            if close_dt <= now:
                continue

            if close_dt > max_close:
                continue

            # ------------------------------------------------
            # DESCRIPCIÓN DEL MERCADO
            # ------------------------------------------------

            market_title = (
                market.get("title")
                or market.get("subtitle")
                or market.get("yes_sub_title")
                or ""
            )

            market_title = str(
                market_title
            ).strip()

            # Si el mercado no tiene título,
            # usamos el evento.

            if not market_title:

                market_title = event_title

            # ------------------------------------------------
            # BID YES
            # ------------------------------------------------

            yes_bid = get_number(
                market.get(
                    "yes_bid_dollars"
                )
            )

            # ------------------------------------------------
            # BID NO
            # ------------------------------------------------

            no_bid = get_number(
                market.get(
                    "no_bid_dollars"
                )
            )

            # ------------------------------------------------
            # VOLUMEN 24H
            # ------------------------------------------------

            volume = get_number(
                market.get(
                    "volume_24h_fp"
                )
            )

            # ------------------------------------------------
            # HORAS RESTANTES
            # ------------------------------------------------

            hours_left = (
                close_dt - now
            ).total_seconds() / 3600

            # ------------------------------------------------
            # FILA
            # ------------------------------------------------

            rows.append({

                "Categoría":
                    category_final,

                "Mercado":
                    market_title,

                "Vencimiento":
                    close_dt,

                "Horas":
                    hours_left,

                "YES Bid":
                    yes_bid,

                "NO Bid":
                    no_bid,

                "Volumen":
                    volume,

                "Ticker":
                    market.get(
                        "ticker",
                        ""
                    )

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
# CONSULTA
# ============================================================

with st.spinner(
    "🔎 Consultando mercados de Kalshi..."
):

    try:

        events = get_events()

        df = build_dataframe(
            events
        )

    except requests.exceptions.RequestException as error:

        st.error(
            "❌ Error de conexión con Kalshi."
        )

        st.code(
            str(error)
        )

        st.stop()

    except Exception as error:

        st.error(
            "❌ Error procesando los datos."
        )

        st.code(
            str(error)
        )

        st.stop()


# ============================================================
# RESULTADO
# ============================================================

if df.empty:

    st.warning(
        "No encontramos mercados de "
        "Economía, Finanzas o Deportes "
        f"que venzan en menos de {MAX_HOURS} horas."
    )

    st.info(
        f"Eventos recibidos desde Kalshi: "
        f"{len(events):,}"
    )

    st.stop()


# ============================================================
# FUNCIÓN PARA MOSTRAR CATEGORÍA
# ============================================================

def show_category(
    dataframe,
    category,
    icon
):

    data = dataframe[
        dataframe["Categoría"] == category
    ].copy()

    # --------------------------------------------------------
    # ORDEN POR VOLUMEN
    # --------------------------------------------------------

    data = data.sort_values(
        "Volumen",
        ascending=False
    ).head(TOP_N)

    # --------------------------------------------------------
    # TÍTULO
    # --------------------------------------------------------

    st.markdown(
        f'<div class="section">'
        f'{icon} {category}'
        f'</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        f'<div class="section-note">'
        f'Top {len(data)} · '
        f'ordenados por volumen de las últimas 24 horas'
        f'</div>',
        unsafe_allow_html=True
    )

    if data.empty:

        st.info(
            "No hay mercados disponibles "
            "en esta categoría."
        )

        return

    # --------------------------------------------------------
    # PREPARAR TABLA
    # --------------------------------------------------------

    table = pd.DataFrame()

    table["Mercado / Evento"] = (
        data["Mercado"]
    )

    table["Vencimiento"] = (
        data["Vencimiento"]
        .apply(
            lambda x:
            x.strftime(
                "%d %b · %H:%M"
            )
        )
    )

    table["YES Bid"] = (
        data["YES Bid"]
        .apply(
            lambda x:
            f"{x:.2f}"
        )
    )

    table["NO Bid"] = (
        data["NO Bid"]
        .apply(
            lambda x:
            f"{x:.2f}"
        )
    )

    # --------------------------------------------------------
    # TABLA
    # --------------------------------------------------------

    st.dataframe(

        table,

        use_container_width=True,

        hide_index=True,

        column_config={

            "Mercado / Evento":
                st.column_config.TextColumn(
                    "Mercado / Evento",
                    width="large"
                ),

            "Vencimiento":
                st.column_config.TextColumn(
                    "Vencimiento",
                    width="medium"
                ),

            "YES Bid":
                st.column_config.TextColumn(
                    "YES Bid",
                    width="small"
                ),

            "NO Bid":
                st.column_config.TextColumn(
                    "NO Bid",
                    width="small"
                )
        }
    )

    st.markdown("---")


# ============================================================
# LAS 3 TABLAS
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
    "Fuente: Kalshi · "
    f"Actualizado {datetime.now().strftime('%d/%m/%Y %H:%M:%S')} · "
    f"Ventana: 0–{MAX_HOURS} horas"
)

import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError


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
SPORTS_SERIES = {
    "KXNFLGAME": "Deportes",
    "KXNCAAFGAME": "Deportes",
    "KXMLBGAME": "Deportes",
    "KXNBAGAME": "Deportes",
}

# Categorías
ECONOMIA_CATEGORIAS = {"economics", "economy"}

# Keywords prioritarios para Economía (¡esta lista faltaba!)
ECONOMIA_KEYWORDS = [
    "cpi", "inflation", "pce", "core",
    "fed", "fomc", "interest rate", "rate cut", "rate hike",
    "jobs", "nonfarm", "payroll", "unemployment", "nfp",
    "gdp", "recession",
    "retail sales", "consumer",
    "housing", "home sales",
    "treasury", "yield",
    "dollar", "dxy",
    "oil", "crude",
    "powell", "jerome",
]


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
    f'''
    <div class="subtitle">
        Top {TOP_N} mercados · vencimiento en menos de {MAX_HOURS} horas<br>
        Ordenados por interés abierto (desempate por volumen 24h)
    </div>
    ''',
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
    """Trae el catálogo completo de series."""
    response = requests.get(f"{BASE_URL}/series", timeout=30)
    response.raise_for_status()
    return response.json().get("series", [])


_series_tickers():
    """
    Devuelve un dict {series_ticker: categoria_final} solo para:
    - Las 4 ligas de Deportes
    - Series de Economía relevantes (filtradas por keywords)
    """
    targets = dict(SPORTS_SERIES)  # las 4 ligas como "Deportes"

    economia_count = 0
    MAX_ECONOMIA = 45          # límite duro para no saturar

    for series in get_all_series():
        if economia_count >= MAX_ECONOMIA:
            break

        ticker = series.get("ticker", "")
        if ticker in targets:
            continue

        category = str(series.get("category", "")).strip().lower()
        title = str(series.get("title", "")).lower()

        if category not in ECONOMIA_CATEGORIAS:
            continue

        # Solo series cuyo título contenga al menos una keyword relevante
        if any(kw in title for kw in ECONOMIA_KEYWORDS):
            targets[ticker] = "Economía"
            economia_count += 1

    return targets

# ============================================================
# ÍNDICES — descubrimiento por TÍTULO de serie
# ============================================================

INDICE_KEYWORDS = {
    "NASDAQ-100": [
        "nasdaq-100", "nasdaq 100", "nasdaq100", "nasdaq", "ndx"
    ],
    "S&P 500": [
        "s&p 500", "s&p500", "s&p", "spx", "inx", "s and p"
    ],
    "Dow Jones": [
        "dow jones", "dow jones industrial", "djia", "dji", "dow"
    ],
}


def discover_index_series():
    """
    Recorre el catálogo de series y encuentra, por coincidencia de
    texto en el título o ticker, todas las series relacionadas a
    NASDAQ-100, S&P 500 y Dow Jones.
    Solo considera categorías Financials/Economics para evitar ruido.
    Devuelve {ticker: (nombre_indice, titulo_serie)}.
    """
    found = {}
    allowed_cats = {"financials", "economics", "finance", "economy"}

    for series in get_all_series():
        ticker = series.get("ticker", "")
        title = str(series.get("title", ""))
        title_lower = title.lower()
        ticker_lower = ticker.lower()
        category = str(series.get("category", "")).strip().lower()

        # Filtrar por categoría para reducir falsos positivos
        if category and category not in allowed_cats:
            continue

        for indice_nombre, keywords in INDICE_KEYWORDS.items():
            if any(kw in title_lower or kw in ticker_lower for kw in keywords):
                found[ticker] = (indice_nombre, title)
                break

    return found








# ============================================================
# PASO 2 — TRAER EVENTOS SOLO DE ESAS SERIES ESPECÍFICAS
# ============================================================

def _fetch_one_series(series_ticker):
    """
    Trae eventos abiertos de UNA serie puntual.
    Cada llamada crea su propia Session (thread-safe).
    Devuelve None si falló, o la lista de eventos si respondió.
    """
    events = []
    cursor = ""

    try:
        with requests.Session() as session:
            for _ in range(10):
                params = {
                    "series_ticker": series_ticker,
                    "status": "open",
                    "with_nested_markets": "true",
                    "limit": 200,
                }
                if cursor:
                    params["cursor"] = cursor

                response = session.get(f"{BASE_URL}/events", params=params, timeout=8)
                response.raise_for_status()

                data = response.json()
                batch = data.get("events", [])

                if not batch:
                    break

                events.extend(batch)
                cursor = data.get("cursor", "")
                if not cursor:
                    break

    except requests.exceptions.RequestException:
        return None

    return events


@st.cache_data(ttl=60)
def get_events_for_all_targets(series_tickers, overall_timeout_seconds=45):
    """
    Trae eventos de VARIAS series en paralelo con tope de tiempo total.
    Devuelve (resultados, num_fallidas, num_total).
    """
    raw_results = {}

    with ThreadPoolExecutor(max_workers=15) as executor:
        futures = {
            executor.submit(_fetch_one_series, ticker): ticker
            for ticker in series_tickers
        }

        try:
            for future in as_completed(futures, timeout=overall_timeout_seconds):
                ticker = futures[future]
                try:
                    raw_results[ticker] = future.result()
                except Exception:
                    raw_results[ticker] = None

        except FuturesTimeoutError:
            # Se acabó el tiempo global
            for future, ticker in futures.items():
                if ticker not in raw_results:
                    raw_results[ticker] = None
                    future.cancel()

    num_fallidas = sum(1 for v in raw_results.values() if v is None)
    num_total = len(raw_results)

    resultados = {
        ticker: (events if events is not None else [])
        for ticker, events in raw_results.items()
    }

    return resultados, num_fallidas, num_total


# ============================================================
# PROCESAR EVENTOS → FILAS DE TABLA
# ============================================================

def build_dataframe(targets):
    now = datetime.now(timezone.utc)
    max_close = now + timedelta(hours=MAX_HOURS)

    rows = []
    total_events_fetched = 0

    events_by_series, num_fallidas, num_total = get_events_for_all_targets(tuple(targets.keys()))

    for series_ticker, category_final in targets.items():
        events = events_by_series.get(series_ticker, [])
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
                if status != "active":
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
                    "EventTicker": event.get("event_ticker", ""),
                    "EventTitle": event_title,
                    "Resultado": market_title,
                    "Vencimiento": close_dt,
                    "YES Bid": yes_bid,
                    "NO Bid": no_bid,
                    "Volumen": volume,
                    "Interés Abierto": open_interest,
                    "Ticker": market.get("ticker", ""),
                })

    columns = [
        "Categoría", "EventTicker", "EventTitle", "Resultado",
        "Vencimiento", "YES Bid", "NO Bid", "Volumen",
        "Interés Abierto", "Ticker",
    ]

    return pd.DataFrame(rows, columns=columns), total_events_fetched, num_fallidas, num_total


def build_indices_dataframe():
    """
    Trae eventos de las series de NASDAQ-100 / S&P 500 / Dow Jones
    y arma dos grupos: los que cierran hoy y los que cierran mañana (UTC).
    """
    index_series = discover_index_series()

    now = datetime.now(timezone.utc)
    hoy = now.date()
    manana = hoy + timedelta(days=1)

    events_by_series, indices_num_fallidas, indices_num_total = get_events_for_all_targets(
        tuple(index_series.keys())
    )

    rows = []

    for series_ticker, (indice_nombre, series_title) in index_series.items():
        events = events_by_series.get(series_ticker, [])

        for event in events:
            event_title = (
                event.get("title")
                or event.get("sub_title")
                or series_title
            )

            markets = event.get("markets", [])

            for market in markets:
                status = str(market.get("status", "")).lower()
                if status != "active":
                    continue

                close_dt = parse_time(market.get("close_time"))
                if close_dt is None:
                    continue

                close_date = close_dt.date()
                if close_date == hoy:
                    grupo = "Hoy"
                elif close_date == manana:
                    grupo = "Mañana"
                else:
                    continue

                market_title = (
                    market.get("yes_sub_title")
                    or market.get("title")
                    or market.get("subtitle")
                    or event_title
                )
                market_title = str(market_title).strip() or event_title

                rows.append({
                    "Grupo": grupo,
                    "Índice": indice_nombre,
                    "EventTicker": event.get("event_ticker", ""),
                    "EventTitle": str(event_title).strip(),
                    "Resultado": market_title,
                    "Vencimiento": close_dt,
                    "YES Bid": get_number(market.get("yes_bid_dollars")),
                    "NO Bid": get_number(market.get("no_bid_dollars")),
                    "Volumen": get_number(market.get("volume_24h_fp")),
                    "Interés Abierto": get_number(market.get("open_interest_fp")),
                })

    columns = [
        "Grupo", "Índice", "EventTicker", "EventTitle", "Resultado",
        "Vencimiento", "YES Bid", "NO Bid", "Volumen", "Interés Abierto",
    ]

    return pd.DataFrame(rows, columns=columns), indices_num_fallidas, indices_num_total


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
        st.caption(f"Consultando {len(targets)} series en paralelo (máx. 45s)...")
        df, total_events_fetched, num_fallidas, num_total = build_dataframe(targets)
        indices_df, indices_num_fallidas, indices_num_total = build_indices_dataframe()

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

if df.empty and indices_df.empty:
    st.warning(
        "No encontramos mercados de Economía, Índices o Deportes "
        f"(ganador del partido: NFL, NCAAF, MLB, NBA) que venzan en "
        f"menos de {MAX_HOURS} horas (o, para Índices, hoy/mañana)."
    )

    if num_fallidas > 0 or indices_num_fallidas > 0:
        st.error(
            f"⚠️ Esto puede ser un problema de conexión, no de datos: "
            f"{num_fallidas}/{num_total} series de Economía/Deportes y "
            f"{indices_num_fallidas}/{indices_num_total} series de Índices "
            f"no respondieron a tiempo. Prueba 'Actualizar datos' de nuevo."
        )
    else:
        st.info(
            f"Todas las series respondieron correctamente "
            f"({num_total} Economía/Deportes, {indices_num_total} Índices) — "
            f"esta vez genuinamente no hay mercados en la ventana pedida."
        )

    st.info(
        f"Series consultadas (Economía/Deportes): {len(targets)} · "
        f"Eventos revisados en esas series: {total_events_fetched:,}"
    )
    st.stop()


# ============================================================
# FUNCIÓN PARA MOSTRAR CATEGORÍA
# ============================================================

def show_category(dataframe, category, icon):
    data = dataframe[dataframe["Categoría"] == category].copy()

    st.markdown(
        f'<div class="section">{icon} {category}</div>',
        unsafe_allow_html=True
    )

    if data.empty:
        st.markdown(
            f'<div class="section-note">'
            f'Top 0 · ordenados por interés abierto '
            f'(desempate por volumen 24h)'
            f'</div>',
            unsafe_allow_html=True
        )
        st.info("No hay mercados disponibles en esta categoría.")
        return

    # Agrupar por evento
    event_rank = (
        data.groupby("EventTicker")
        .agg(
            InteresEvento=("Interés Abierto", "sum"),
            VolumenEvento=("Volumen", "sum"),
        )
        .reset_index()
        .sort_values(
            ["InteresEvento", "VolumenEvento"],
            ascending=[False, False]
        )
        .head(TOP_N)
    )

    rows_out = []

    for _, event_row in event_rank.iterrows():
        event_ticker = event_row["EventTicker"]
        subset = data[data["EventTicker"] == event_ticker]

        representative = subset.sort_values(
            ["Interés Abierto", "Volumen"],
            ascending=[False, False]
        ).iloc[0]

        event_title = representative["EventTitle"]
        resultado = representative["Resultado"]

        if resultado.strip() and resultado.strip() != event_title.strip():
            nombre_mostrado = f"{event_title} — {resultado}"
        else:
            nombre_mostrado = event_title

        rows_out.append({
            "Mercado / Evento": nombre_mostrado,
            "Vencimiento": representative["Vencimiento"],
            "YES Bid": representative["YES Bid"],
            "NO Bid": representative["NO Bid"],
        })

    st.markdown(
        f'<div class="section-note">'
        f'Top {len(rows_out)} eventos · ordenados por interés abierto '
        f'(desempate por volumen 24h) · el resultado mostrado es el '
        f'de mayor interés abierto dentro de cada evento'
        f'</div>',
        unsafe_allow_html=True
    )

    table = pd.DataFrame(rows_out)

    table["Vencimiento"] = table["Vencimiento"].apply(
        lambda x: x.strftime("%d %b · %H:%M")
    )
    table["YES Bid"] = table["YES Bid"].apply(format_pct)
    table["NO Bid"] = table["NO Bid"].apply(format_pct)

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


def show_indices_group(indices_dataframe, grupo, titulo, icon):
    """
    Muestra un grupo (Hoy / Mañana) de mercados de índices.
    """
    data = indices_dataframe[indices_dataframe["Grupo"] == grupo].copy()

    st.markdown(
        f'<div class="section">{icon} {titulo}</div>',
        unsafe_allow_html=True
    )

    if data.empty:
        st.markdown(
            '<div class="section-note">Sin mercados en este grupo</div>',
            unsafe_allow_html=True
        )
        st.info("No hay mercados de índices disponibles en este grupo.")
        return

    rows_out = []

    for event_ticker in data["EventTicker"].unique():
        subset = data[data["EventTicker"] == event_ticker]

        representative = subset.sort_values(
            ["Interés Abierto", "Volumen"],
            ascending=[False, False]
        ).iloc[0]

        event_title = representative["EventTitle"]
        resultado = representative["Resultado"]

        if resultado.strip() and resultado.strip() != event_title.strip():
            nombre_mostrado = f"{event_title} — {resultado}"
        else:
            nombre_mostrado = event_title

        rows_out.append({
            "Índice": representative["Índice"],
            "Mercado / Evento": nombre_mostrado,
            "Vencimiento": representative["Vencimiento"],
            "YES Bid": representative["YES Bid"],
            "NO Bid": representative["NO Bid"],
        })

    st.markdown(
        f'<div class="section-note">{len(rows_out)} evento(s)</div>',
        unsafe_allow_html=True
    )

    table = pd.DataFrame(rows_out).sort_values("Índice")

    table["Vencimiento"] = table["Vencimiento"].apply(
        lambda x: x.strftime("%d %b · %H:%M")
    )
    table["YES Bid"] = table["YES Bid"].apply(format_pct)
    table["NO Bid"] = table["NO Bid"].apply(format_pct)

    st.dataframe(
        table,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Índice": st.column_config.TextColumn("Índice", width="small"),
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
# LAS TABLAS
# ============================================================

show_category(df, "Economía", "📈")
show_indices_group(indices_df, "Hoy", "Índices — Cierre de Hoy", "💰")
show_indices_group(indices_df, "Mañana", "Índices — Cierre de Mañana", "💰")
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

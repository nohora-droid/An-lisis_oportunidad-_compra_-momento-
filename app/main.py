# =============================================================
# main.py — Entrada principal de la app Streamlit
# BIA Energy — Herramienta de Inteligencia de Compra
# =============================================================

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
import pandas as pd
from scripts.data_loader import cargar_todo
from scripts.analisis import calcular_percentil_pb
from scripts.indexador_ipp import meses_disponibles

# ── Configuración de página ──────────────────────────────────
st.set_page_config(
    page_title="BIA Energy — Compra Inteligente",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS personalizado ────────────────────────────────────────
st.markdown("""
<style>
    .metric-card {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 16px 20px;
        margin: 6px 0;
    }
    .metric-card h3 { margin: 0; font-size: 0.85rem; color: #64748b; }
    .metric-card p  { margin: 4px 0 0; font-size: 1.6rem; font-weight: 700; color: #1e293b; }
    .señal-verde { color: #16a34a; font-weight: 700; }
    .señal-roja  { color: #dc2626; font-weight: 700; }
    .señal-amarilla { color: #d97706; font-weight: 700; }
    .sidebar-info { font-size: 0.8rem; color: #94a3b8; padding: 8px; }
    [data-testid="stMetricValue"] { font-size: 1.8rem !important; }
</style>
""", unsafe_allow_html=True)

# ── Carga de datos (cacheada) ────────────────────────────────
@st.cache_data(ttl=3600, show_spinner="Cargando datos de mercado...", hash_funcs={})
def _cargar(version: int = 2):          # incrementa 'version' para forzar recarga
    return cargar_todo()

datos = _cargar( 
    $n = [int](# =============================================================
# main.py — Entrada principal de la app Streamlit
# BIA Energy — Herramienta de Inteligencia de Compra
# =============================================================

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
import pandas as pd
from scripts.data_loader import cargar_todo
from scripts.analisis import calcular_percentil_pb
from scripts.indexador_ipp import meses_disponibles

# ── Configuración de página ──────────────────────────────────
st.set_page_config(
    page_title="BIA Energy — Compra Inteligente",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS personalizado ────────────────────────────────────────
st.markdown("""
<style>
    .metric-card {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 16px 20px;
        margin: 6px 0;
    }
    .metric-card h3 { margin: 0; font-size: 0.85rem; color: #64748b; }
    .metric-card p  { margin: 4px 0 0; font-size: 1.6rem; font-weight: 700; color: #1e293b; }
    .señal-verde { color: #16a34a; font-weight: 700; }
    .señal-roja  { color: #dc2626; font-weight: 700; }
    .señal-amarilla { color: #d97706; font-weight: 700; }
    .sidebar-info { font-size: 0.8rem; color: #94a3b8; padding: 8px; }
    [data-testid="stMetricValue"] { font-size: 1.8rem !important; }
</style>
""", unsafe_allow_html=True)

# ── Carga de datos (cacheada) ────────────────────────────────
@st.cache_data(ttl=3600, show_spinner="Cargando datos de mercado...", hash_funcs={})
def _cargar(version: int = 2):          # incrementa 'version' para forzar recarga
    return cargar_todo()

datos = _cargar(version=3)
pb          = datos["pb"]
ofertas     = datos["ofertas"]
master      = datos["master"]
ipp         = datos["ipp"]
pronostico  = datos.get("pronostico", pd.DataFrame())

# Guardar en session_state para que las páginas lo usen
st.session_state["pb"]          = pb
st.session_state["ofertas"]     = ofertas
st.session_state["master"]      = master
st.session_state["ipp"]         = ipp
st.session_state["pronostico"]  = pronostico

# ── Sidebar ──────────────────────────────────────────────────
with st.sidebar:
    st.image("https://via.placeholder.com/200x60/1e3a5f/ffffff?text=BIA+ENERGY",
             use_column_width=True)
    st.markdown("---")
    st.markdown("**Navega por las secciones:**")
    st.markdown("""
    - 🏠 **Inicio** (esta página)
    - ⏱️ **¿Cuándo Comprar?** — timing óptimo
    - 🤝 **Análisis de Agentes** — perfil por generador
    - 🔔 **Alertas de Mercado** — señal PB actual
    - 📋 **Vendedores Libres** — no adjudicados
    - 🔮 **Proyección PB** — pronóstico escenarios
    """)
    # ── Selector global de IPP ───────────────────────────────
    st.markdown("---")
    st.markdown("**⚙️ Indexación de precios (IPP)**")
    meses_ipp = meses_disponibles(ipp) if len(ipp) > 0 else []
    if meses_ipp:
        mes_idx_global = st.selectbox(
            "Mes objetivo de indexación",
            options=meses_ipp,
            index=len(meses_ipp) - 1,
            key="mes_idx_global_widget",
            help="Todos los precios se convierten a $/kWh del mes seleccionado.",
        )
        # Obtener valor numérico del IPP para ese mes
        col_fecha_ipp = next((c for c in ipp.columns if c.lower() == "fecha"), None)
        col_val_ipp   = next((c for c in ipp.columns if c.lower() == "ipp"), None)
        if col_fecha_ipp and col_val_ipp:
            ipp_val_map = dict(zip(
                pd.to_datetime(ipp[col_fecha_ipp]).dt.to_period("M").astype(str),
                ipp[col_val_ipp]
            ))
            ipp_valor_global = ipp_val_map.get(mes_idx_global, None)
            if ipp_valor_global:
                st.caption(f"IPP {mes_idx_global}: **{ipp_valor_global:.2f}**")
        else:
            ipp_valor_global = None
    else:
        mes_idx_global   = None
        ipp_valor_global = None
        st.caption("⚠️ Serie IPP no disponible")

    # Guardar en session_state para uso global
    st.session_state["mes_idx_global"]   = mes_idx_global
    st.session_state["ipp_valor_global"] = ipp_valor_global

    # ── Filtro global de audiencias ──────────────────────────
    st.markdown("---")
    st.markdown("**🔎 Filtro de audiencias**")
    todas_audiencias = sorted(ofertas["audiencia_id"].unique().tolist())
    audiencias_sel = st.multiselect(
        "Incluir audiencias",
        options=todas_audiencias,
        default=todas_audiencias,
        key="audiencias_sel_global",
        help="Deja todas marcadas para analizar el histórico completo.",
        placeholder="Buscar audiencia...",
    )
    if not audiencias_sel:
        audiencias_sel = todas_audiencias   # si borra todo, usa todas
    st.session_state["audiencias_sel"] = audiencias_sel
    st.caption(f"{len(audiencias_sel)} de {len(todas_audiencias)} audiencias seleccionadas")

    # ── Datos de contexto ────────────────────────────────────
    st.markdown("---")
    pb_fecha = pb["fecha"].max().date()
    st.markdown(f"<div class='sidebar-info'>📅 PB hasta: <b>{pb_fecha}</b></div>",
                unsafe_allow_html=True)
    st.markdown(f"<div class='sidebar-info'>📊 Procesos: <b>{len(master)}</b></div>",
                unsafe_allow_html=True)
    st.markdown(f"<div class='sidebar-info'>🏭 Agentes: <b>{ofertas['agente_nombre'].nunique()}</b></div>",
                unsafe_allow_html=True)

# ── Header ───────────────────────────────────────────────────
st.title("⚡ BIA Energy — Inteligencia de Compra")
st.markdown("Herramienta de análisis para decisiones de compra de energía en el mercado colombiano.")
st.markdown("---")

# ── Estado actual del mercado ────────────────────────────────
estado_pb = calcular_percentil_pb(pb)

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("PB hoy", f"${estado_pb['pb_actual']:,.0f}/kWh",
              delta=f"{estado_pb['tendencia_30d']:+.1f} $/kWh (tendencia 30d)")

with col2:
    st.metric("PB promedio 30d", f"${estado_pb['pb_30d']:,.0f}/kWh")

with col3:
    st.metric("PB promedio 90d", f"${estado_pb['pb_90d']:,.0f}/kWh")

with col4:
    pct = estado_pb["percentil"]
    color = "normal" if pct >= 70 else ("off" if pct < 40 else "normal")
    st.metric("Percentil histórico", f"{pct:.0f}°",
              delta=estado_pb["direccion"])

# ── Señal de compra ──────────────────────────────────────────
st.markdown("### 🎯 Señal de Mercado Actual")
señal = estado_pb["señal"]
if "FUERTE" in señal:
    st.success(señal)
elif "MODERADA" in señal:
    st.warning(señal)
else:
    st.error(señal)

st.markdown(f"""
> **¿Qué significa esto?**
> La PB está en el **percentil {pct:.0f}°** de su historia reciente.
> {'Una PB alta históricamente es un buen momento para contratar energía a largo plazo, ya que los generadores tienen incentivo de asegurar ingresos por debajo de la bolsa.' if pct >= 60 else 'Una PB baja puede indicar que los generadores no tienen presión para contratar. Considera esperar o negociar en momentos de mayor tensión en el mercado.'}
""")

st.markdown("---")

# ── Resumen del mercado ──────────────────────────────────────
st.markdown("### 📊 Resumen del Mercado Histórico")

col_a, col_b, col_c = st.columns(3)

master_adj = master[master["precio_adj_prom"].notna()]

with col_a:
    st.markdown("**Últimos precios adjudicados**")
    ult = master_adj.sort_values("fecha_audiencia", ascending=False).head(5)[
        ["audiencia_id", "fecha_audiencia", "precio_adj_prom", "adjudicatario"]
    ].copy()
    ult["fecha_audiencia"] = ult["fecha_audiencia"].dt.strftime("%Y-%m-%d")
    ult["precio_adj_prom"] = ult["precio_adj_prom"].map("${:,.0f}".format)
    st.dataframe(ult.rename(columns={
        "audiencia_id": "Proceso",
        "fecha_audiencia": "Fecha",
        "precio_adj_prom": "Precio adj.",
        "adjudicatario": "Adjudicatario",
    }), hide_index=True, use_container_width=True)

with col_b:
    st.markdown("**Top 5 agentes más activos**")
    top_ag = (
        ofertas.groupby("agente_nombre")
        .agg(ofertas=("audiencia_id","count"), adj_pct=("adjudicada","mean"))
        .nlargest(5, "ofertas")
        .reset_index()
    )
    top_ag["adj_pct"] = (top_ag["adj_pct"] * 100).map("{:.0f}%".format)
    st.dataframe(top_ag.rename(columns={
        "agente_nombre": "Agente",
        "ofertas": "N° ofertas",
        "adj_pct": "% adj.",
    }), hide_index=True, use_container_width=True)

with col_c:
    st.markdown("**Actividad reciente (90d)**")
    corte90 = master["fecha_audiencia"].max() - pd.Timedelta(days=90)
    rec = master[master["fecha_audiencia"] >= corte90]
    st.metric("Procesos (90d)", len(rec))
    st.metric("Con adjudicación", rec["precio_adj_prom"].notna().sum())
    st.metric("Precio adj. prom.", f"${rec['precio_adj_prom'].mean():,.0f}/kWh"
              if rec["precio_adj_prom"].notna().any() else "N/D")

# ── Widget de pronóstico ─────────────────────────────────────
if len(pronostico) > 0 and "base_p50" in pronostico.columns:
    st.markdown("### 🔮 Pronóstico PB — próximos 30 días")
    pron30 = pronostico.head(30)
    pb_actual = pb["pb_prom_kwh"].iloc[-1]
    pron_p50_30 = pron30["base_p50"].mean()
    pron_max_30 = pron30["base_p90"].max()
    pron_min_30 = pron30["base_p10"].min()

    col_p1, col_p2, col_p3, col_p4 = st.columns(4)
    with col_p1:
        st.metric("PB actual", f"${pb_actual:,.0f}/kWh")
    with col_p2:
        delta30 = pron_p50_30 - pb_actual
        st.metric("Pronóstico P50 (30d)", f"${pron_p50_30:,.0f}/kWh",
                  delta=f"{delta30:+,.0f} $/kWh")
    with col_p3:
        st.metric("Pico esperado P90", f"${pron_max_30:,.0f}/kWh")
    with col_p4:
        st.metric("Piso esperado P10", f"${pron_min_30:,.0f}/kWh")

    st.caption("▶ Ver análisis completo en **🔮 Proyección PB**")

st.markdown("---")
st.markdown(
    "<div style='text-align:center;color:#94a3b8;font-size:0.8rem;'>"
    "BIA Energy S.A.S. E.S.P. — Herramienta interna de inteligencia de mercado | "
    "Datos: SICEP + Metabase"
    "</div>",
    unsafe_allow_html=True
)
.Value -replace 'version=','') + 1
    "version=$n"
)
pb          = datos["pb"]
ofertas     = datos["ofertas"]
master      = datos["master"]
ipp         = datos["ipp"]
pronostico  = datos.get("pronostico", pd.DataFrame())

# Guardar en session_state para que las páginas lo usen
st.session_state["pb"]          = pb
st.session_state["ofertas"]     = ofertas
st.session_state["master"]      = master
st.session_state["ipp"]         = ipp
st.session_state["pronostico"]  = pronostico

# ── Sidebar ──────────────────────────────────────────────────
with st.sidebar:
    st.image("https://via.placeholder.com/200x60/1e3a5f/ffffff?text=BIA+ENERGY",
             use_column_width=True)
    st.markdown("---")
    st.markdown("**Navega por las secciones:**")
    st.markdown("""
    - 🏠 **Inicio** (esta página)
    - ⏱️ **¿Cuándo Comprar?** — timing óptimo
    - 🤝 **Análisis de Agentes** — perfil por generador
    - 🔔 **Alertas de Mercado** — señal PB actual
    - 📋 **Vendedores Libres** — no adjudicados
    - 🔮 **Proyección PB** — pronóstico escenarios
    """)
    # ── Selector global de IPP ───────────────────────────────
    st.markdown("---")
    st.markdown("**⚙️ Indexación de precios (IPP)**")
    meses_ipp = meses_disponibles(ipp) if len(ipp) > 0 else []
    if meses_ipp:
        mes_idx_global = st.selectbox(
            "Mes objetivo de indexación",
            options=meses_ipp,
            index=len(meses_ipp) - 1,
            key="mes_idx_global_widget",
            help="Todos los precios se convierten a $/kWh del mes seleccionado.",
        )
        # Obtener valor numérico del IPP para ese mes
        col_fecha_ipp = next((c for c in ipp.columns if c.lower() == "fecha"), None)
        col_val_ipp   = next((c for c in ipp.columns if c.lower() == "ipp"), None)
        if col_fecha_ipp and col_val_ipp:
            ipp_val_map = dict(zip(
                pd.to_datetime(ipp[col_fecha_ipp]).dt.to_period("M").astype(str),
                ipp[col_val_ipp]
            ))
            ipp_valor_global = ipp_val_map.get(mes_idx_global, None)
            if ipp_valor_global:
                st.caption(f"IPP {mes_idx_global}: **{ipp_valor_global:.2f}**")
        else:
            ipp_valor_global = None
    else:
        mes_idx_global   = None
        ipp_valor_global = None
        st.caption("⚠️ Serie IPP no disponible")

    # Guardar en session_state para uso global
    st.session_state["mes_idx_global"]   = mes_idx_global
    st.session_state["ipp_valor_global"] = ipp_valor_global

    # ── Filtro global de audiencias ──────────────────────────
    st.markdown("---")
    st.markdown("**🔎 Filtro de audiencias**")
    todas_audiencias = sorted(ofertas["audiencia_id"].unique().tolist())
    audiencias_sel = st.multiselect(
        "Incluir audiencias",
        options=todas_audiencias,
        default=todas_audiencias,
        key="audiencias_sel_global",
        help="Deja todas marcadas para analizar el histórico completo.",
        placeholder="Buscar audiencia...",
    )
    if not audiencias_sel:
        audiencias_sel = todas_audiencias   # si borra todo, usa todas
    st.session_state["audiencias_sel"] = audiencias_sel
    st.caption(f"{len(audiencias_sel)} de {len(todas_audiencias)} audiencias seleccionadas")

    # ── Datos de contexto ────────────────────────────────────
    st.markdown("---")
    pb_fecha = pb["fecha"].max().date()
    st.markdown(f"<div class='sidebar-info'>📅 PB hasta: <b>{pb_fecha}</b></div>",
                unsafe_allow_html=True)
    st.markdown(f"<div class='sidebar-info'>📊 Procesos: <b>{len(master)}</b></div>",
                unsafe_allow_html=True)
    st.markdown(f"<div class='sidebar-info'>🏭 Agentes: <b>{ofertas['agente_nombre'].nunique()}</b></div>",
                unsafe_allow_html=True)

# ── Header ───────────────────────────────────────────────────
st.title("⚡ BIA Energy — Inteligencia de Compra")
st.markdown("Herramienta de análisis para decisiones de compra de energía en el mercado colombiano.")
st.markdown("---")

# ── Estado actual del mercado ────────────────────────────────
estado_pb = calcular_percentil_pb(pb)

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("PB hoy", f"${estado_pb['pb_actual']:,.0f}/kWh",
              delta=f"{estado_pb['tendencia_30d']:+.1f} $/kWh (tendencia 30d)")

with col2:
    st.metric("PB promedio 30d", f"${estado_pb['pb_30d']:,.0f}/kWh")

with col3:
    st.metric("PB promedio 90d", f"${estado_pb['pb_90d']:,.0f}/kWh")

with col4:
    pct = estado_pb["percentil"]
    color = "normal" if pct >= 70 else ("off" if pct < 40 else "normal")
    st.metric("Percentil histórico", f"{pct:.0f}°",
              delta=estado_pb["direccion"])

# ── Señal de compra ──────────────────────────────────────────
st.markdown("### 🎯 Señal de Mercado Actual")
señal = estado_pb["señal"]
if "FUERTE" in señal:
    st.success(señal)
elif "MODERADA" in señal:
    st.warning(señal)
else:
    st.error(señal)

st.markdown(f"""
> **¿Qué significa esto?**
> La PB está en el **percentil {pct:.0f}°** de su historia reciente.
> {'Una PB alta históricamente es un buen momento para contratar energía a largo plazo, ya que los generadores tienen incentivo de asegurar ingresos por debajo de la bolsa.' if pct >= 60 else 'Una PB baja puede indicar que los generadores no tienen presión para contratar. Considera esperar o negociar en momentos de mayor tensión en el mercado.'}
""")

st.markdown("---")

# ── Resumen del mercado ──────────────────────────────────────
st.markdown("### 📊 Resumen del Mercado Histórico")

col_a, col_b, col_c = st.columns(3)

master_adj = master[master["precio_adj_prom"].notna()]

with col_a:
    st.markdown("**Últimos precios adjudicados**")
    ult = master_adj.sort_values("fecha_audiencia", ascending=False).head(5)[
        ["audiencia_id", "fecha_audiencia", "precio_adj_prom", "adjudicatario"]
    ].copy()
    ult["fecha_audiencia"] = ult["fecha_audiencia"].dt.strftime("%Y-%m-%d")
    ult["precio_adj_prom"] = ult["precio_adj_prom"].map("${:,.0f}".format)
    st.dataframe(ult.rename(columns={
        "audiencia_id": "Proceso",
        "fecha_audiencia": "Fecha",
        "precio_adj_prom": "Precio adj.",
        "adjudicatario": "Adjudicatario",
    }), hide_index=True, use_container_width=True)

with col_b:
    st.markdown("**Top 5 agentes más activos**")
    top_ag = (
        ofertas.groupby("agente_nombre")
        .agg(ofertas=("audiencia_id","count"), adj_pct=("adjudicada","mean"))
        .nlargest(5, "ofertas")
        .reset_index()
    )
    top_ag["adj_pct"] = (top_ag["adj_pct"] * 100).map("{:.0f}%".format)
    st.dataframe(top_ag.rename(columns={
        "agente_nombre": "Agente",
        "ofertas": "N° ofertas",
        "adj_pct": "% adj.",
    }), hide_index=True, use_container_width=True)

with col_c:
    st.markdown("**Actividad reciente (90d)**")
    corte90 = master["fecha_audiencia"].max() - pd.Timedelta(days=90)
    rec = master[master["fecha_audiencia"] >= corte90]
    st.metric("Procesos (90d)", len(rec))
    st.metric("Con adjudicación", rec["precio_adj_prom"].notna().sum())
    st.metric("Precio adj. prom.", f"${rec['precio_adj_prom'].mean():,.0f}/kWh"
              if rec["precio_adj_prom"].notna().any() else "N/D")

# ── Widget de pronóstico ─────────────────────────────────────
if len(pronostico) > 0 and "base_p50" in pronostico.columns:
    st.markdown("### 🔮 Pronóstico PB — próximos 30 días")
    pron30 = pronostico.head(30)
    pb_actual = pb["pb_prom_kwh"].iloc[-1]
    pron_p50_30 = pron30["base_p50"].mean()
    pron_max_30 = pron30["base_p90"].max()
    pron_min_30 = pron30["base_p10"].min()

    col_p1, col_p2, col_p3, col_p4 = st.columns(4)
    with col_p1:
        st.metric("PB actual", f"${pb_actual:,.0f}/kWh")
    with col_p2:
        delta30 = pron_p50_30 - pb_actual
        st.metric("Pronóstico P50 (30d)", f"${pron_p50_30:,.0f}/kWh",
                  delta=f"{delta30:+,.0f} $/kWh")
    with col_p3:
        st.metric("Pico esperado P90", f"${pron_max_30:,.0f}/kWh")
    with col_p4:
        st.metric("Piso esperado P10", f"${pron_min_30:,.0f}/kWh")

    st.caption("▶ Ver análisis completo en **🔮 Proyección PB**")

st.markdown("---")
st.markdown(
    "<div style='text-align:center;color:#94a3b8;font-size:0.8rem;'>"
    "BIA Energy S.A.S. E.S.P. — Herramienta interna de inteligencia de mercado | "
    "Datos: SICEP + Metabase"
    "</div>",
    unsafe_allow_html=True
)

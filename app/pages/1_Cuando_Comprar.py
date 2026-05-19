# =============================================================
# Página 1: ¿Cuándo Comprar? — Timing óptimo de contratación
# =============================================================

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from scripts.analisis import analisis_timing, mejor_mes_para_vigencia, proyectar_mejor_momento

st.set_page_config(page_title="¿Cuándo Comprar? — BIA Energy", page_icon="⏱️", layout="wide")

# ── Datos desde session_state ────────────────────────────────
if "master" not in st.session_state:
    st.warning("⚠️ Regresa a la página principal para cargar los datos.")
    st.stop()

pb      = st.session_state["pb"]
master  = st.session_state["master"]

st.title("⏱️ ¿Cuándo es el mejor momento para abrir un proceso?")
st.markdown("""
Analiza el **spread histórico** entre el precio adjudicado y el precio de bolsa (PB)
para identificar en qué meses del año se han conseguido mejores condiciones de compra.

> 💡 **Spread negativo** = se contrató **por debajo** de la PB → buen negocio.
> **Spread positivo** = se contrató **por encima** de la PB.
""")
st.markdown("---")

# ── Filtros ──────────────────────────────────────────────────
col_f1, col_f2, col_f3 = st.columns([1, 1, 2])

años_vigencia = sorted(master["año_vigencia"].dropna().unique().astype(int).tolist())
años_vigencia_opciones = ["Todos"] + [str(y) for y in años_vigencia]

with col_f1:
    año_sel = st.selectbox(
        "Año de vigencia requerido",
        options=años_vigencia_opciones,
        index=0,
        help="Si ya sabes qué año necesitas cubrir, selecciónalo para ver patrones específicos."
    )

with col_f2:
    años_historico = sorted(master["año_audiencia"].dropna().unique().astype(int).tolist())
    años_hist_sel  = st.multiselect(
        "Filtrar por año de audiencia",
        options=años_historico,
        default=años_historico,
    )

with col_f3:
    mercados_disp = master["mercado"].dropna().unique().tolist() if "mercado" in master.columns else []
    if mercados_disp:
        mercado_sel = st.multiselect("Mercado", options=mercados_disp, default=mercados_disp)
    else:
        mercado_sel = []

# Aplicar filtros
df_filt = master[
    master["año_audiencia"].isin(años_hist_sel) &
    master["precio_adj_prom"].notna()
].copy()
if mercado_sel and "mercado" in df_filt.columns:
    df_filt = df_filt[df_filt["mercado"].isin(mercado_sel)]

st.markdown("---")

# ── Si hay año de vigencia seleccionado ─────────────────────
if año_sel != "Todos":
    año_int = int(año_sel)
    proyeccion = proyectar_mejor_momento(master, pb, año_int)

    st.markdown(f"### 🎯 Proyección para vigencia {año_int}")
    st.info(proyeccion["recomendacion"])

    col_e1, col_e2 = st.columns(2)
    with col_e1:
        rank = proyeccion["ranking_meses"]
        if len(rank) > 0:
            fig = go.Figure()
            colores = ["#16a34a" if s <= 0 else "#dc2626" for s in rank["spread_prom"]]
            fig.add_bar(
                x=rank.index,
                y=rank["spread_prom"],
                marker_color=colores,
                text=[f"${v:,.0f}" for v in rank["spread_prom"]],
                textposition="outside",
            )
            fig.add_hline(y=0, line_dash="dash", line_color="black", line_width=1)
            fig.update_layout(
                title=f"Spread promedio por mes — vigencia {año_int}",
                yaxis_title="Spread $/kWh (adj - PB 30d)",
                xaxis_title="Mes de audiencia",
                showlegend=False,
                height=380,
                plot_bgcolor="white",
                yaxis=dict(gridcolor="#f1f5f9"),
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info(f"Sin datos históricos para vigencia {año_int}.")

    with col_e2:
        if len(rank) > 0:
            st.dataframe(
                rank.rename(columns={
                    "n_procesos": "N° procesos",
                    "spread_prom": "Spread prom $/kWh",
                    "precio_adj": "Precio adj. $/kWh",
                    "pb_30d_prom": "PB 30d $/kWh",
                }).style.background_gradient(subset=["Spread prom $/kWh"], cmap="RdYlGn_r"),
                use_container_width=True,
            )

    st.markdown("---")

# ── Análisis general de timing ───────────────────────────────
st.markdown("### 📅 Estacionalidad histórica general")

timing = analisis_timing(df_filt, pb)

tab1, tab2, tab3 = st.tabs(["📊 Spread por mes", "📈 PB estacional", "📋 Detalle por proceso"])

with tab1:
    por_mes = timing["por_mes"]
    fig = go.Figure()

    colores = ["#16a34a" if s <= 0 else "#dc2626" for s in por_mes["spread_prom"]]
    fig.add_bar(
        x=por_mes.index,
        y=por_mes["spread_prom"],
        marker_color=colores,
        name="Spread promedio",
        text=[f"${v:,.0f}" for v in por_mes["spread_prom"]],
        textposition="outside",
        customdata=por_mes[["n_procesos", "precio_adj_prom"]].values,
        hovertemplate=(
            "<b>%{x}</b><br>"
            "Spread: %{y:,.0f} $/kWh<br>"
            "N° procesos: %{customdata[0]}<br>"
            "Precio adj. prom: %{customdata[1]:,.0f} $/kWh"
            "<extra></extra>"
        ),
    )
    fig.add_bar(
        x=por_mes.index,
        y=por_mes["spread_mediana"],
        name="Spread mediana",
        marker_color="rgba(100,100,100,0.3)",
        marker_line_color="gray",
        marker_line_width=1,
    )
    fig.add_hline(y=0, line_dash="dash", line_color="black", line_width=1.5,
                  annotation_text="Break-even vs PB")
    fig.update_layout(
        title="Spread histórico: Precio adjudicado − PB 30 días previos, por mes de apertura",
        yaxis_title="$/kWh",
        xaxis_title="Mes de apertura del proceso",
        barmode="group",
        height=420,
        plot_bgcolor="white",
        yaxis=dict(gridcolor="#f1f5f9"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig, use_container_width=True)

    col_a, col_b, col_c = st.columns(3)
    mejor = por_mes.index[0]
    peor  = por_mes.index[-1]
    with col_a:
        st.success(f"✅ **Mejor mes históricamente:** {mejor}  \nSpread: ${por_mes['spread_prom'].iloc[0]:,.0f}/kWh")
    with col_b:
        st.error(f"❌ **Peor mes históricamente:** {peor}  \nSpread: ${por_mes['spread_prom'].iloc[-1]:,.0f}/kWh")
    with col_c:
        n_total = por_mes["n_procesos"].sum()
        st.info(f"📊 **Base histórica:** {n_total} procesos analizados")

with tab2:
    pb_est = timing["pb_estacional"]
    fig2 = go.Figure()
    fig2.add_scatter(
        x=pb_est.index, y=pb_est["pb_prom"],
        mode="lines+markers+text",
        name="PB promedio",
        line=dict(color="#2563eb", width=2.5),
        marker=dict(size=8),
        text=[f"${v:,.0f}" for v in pb_est["pb_prom"]],
        textposition="top center",
    )
    fig2.add_scatter(
        x=list(pb_est.index) + list(pb_est.index[::-1]),
        y=list(pb_est["pb_p75"]) + list(pb_est["pb_p25"][::-1]),
        fill="toself",
        fillcolor="rgba(37,99,235,0.1)",
        line=dict(color="rgba(255,255,255,0)"),
        name="Rango P25-P75",
        showlegend=True,
    )
    fig2.update_layout(
        title="Estacionalidad del Precio de Bolsa — promedio histórico por mes",
        yaxis_title="$/kWh",
        height=380,
        plot_bgcolor="white",
        yaxis=dict(gridcolor="#f1f5f9"),
    )
    st.plotly_chart(fig2, use_container_width=True)

    st.markdown("""
    > **¿Cómo leer esto?** Los meses **Sep-Oct** históricamente tienen PB más alta
    > (fenómeno Niño, estiaje). En esos momentos los generadores tienen mayor incentivo
    > para contratar a futuro, lo que suele resultar en mejores precios para el comprador.
    """)

with tab3:
    df_det = df_filt[[
        "audiencia_id", "fecha_audiencia", "comprador", "año_vigencia",
        "precio_adj_prom", "pb_prom_30d", "spread_vs_pb_30d",
        "pb_tendencia", "horizonte_meses"
    ]].sort_values("fecha_audiencia", ascending=False).copy()
    df_det["fecha_audiencia"] = df_det["fecha_audiencia"].dt.strftime("%Y-%m-%d")

    # Filtro de búsqueda rápida
    busqueda = st.text_input("🔍 Buscar proceso o comprador", "")
    if busqueda:
        mask = (
            df_det["audiencia_id"].str.contains(busqueda.upper(), na=False) |
            df_det["comprador"].str.contains(busqueda.upper(), na=False)
        )
        df_det = df_det[mask]

    st.dataframe(
        df_det.rename(columns={
            "audiencia_id": "Proceso",
            "fecha_audiencia": "Fecha audiencia",
            "comprador": "Comprador",
            "año_vigencia": "Año vigencia",
            "precio_adj_prom": "Precio adj.",
            "pb_prom_30d": "PB 30d",
            "spread_vs_pb_30d": "Spread",
            "pb_tendencia": "PB tendencia",
            "horizonte_meses": "Horizonte (m)",
        }),
        use_container_width=True,
        hide_index=True,
    )

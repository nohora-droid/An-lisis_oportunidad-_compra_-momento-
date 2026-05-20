# =============================================================
# Página 3: Alertas de Mercado — ¿Es buen momento para comprar?
# =============================================================

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from scripts.analisis import calcular_percentil_pb

st.set_page_config(page_title="Alertas de Mercado — BIA Energy", page_icon="🔔", layout="wide")

if "pb" not in st.session_state:
    st.warning("⚠️ Regresa a la página principal para cargar los datos.")
    st.stop()

pb         = st.session_state["pb"]
master     = st.session_state["master"]
pronostico = st.session_state.get("pronostico", pd.DataFrame())

st.title("🔔 Alertas de Mercado")
st.markdown("""
Monitoreo del **Precio de Bolsa (PB)** histórico y actual para identificar
ventanas óptimas de contratación.

> **Lógica:** Cuando la PB está **alta** en términos históricos, los generadores
> tienen incentivo de asegurar ingresos a futuro → **mejor momento** para abrir procesos.
""")
st.markdown("---")

# ── Estado actual ────────────────────────────────────────────
estado = calcular_percentil_pb(pb)

st.markdown("### 📡 Estado actual del mercado")

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.metric("PB más reciente", f"${estado['pb_actual']:,.0f}/kWh")
with col2:
    st.metric("Promedio 30d", f"${estado['pb_30d']:,.0f}/kWh")
with col3:
    st.metric("Promedio 90d", f"${estado['pb_90d']:,.0f}/kWh")
with col4:
    st.metric("Percentil histórico", f"{estado['percentil']:.0f}°",
              delta=estado["direccion"])
with col5:
    st.metric("Fecha de referencia", str(estado["fecha_ref"]))

señal = estado["señal"]
if "FUERTE" in señal:
    st.success(f"### {señal}")
elif "MODERADA" in señal:
    st.warning(f"### {señal}")
else:
    st.error(f"### {señal}")

st.markdown("---")

# ── Serie histórica PB con zonas de alerta ──────────────────
st.markdown("### 📈 Histórico del Precio de Bolsa con zonas de oportunidad")

ventana_dias = st.slider(
    "Ventana de referencia (días)", min_value=180, max_value=1500,
    value=1095, step=90, help="Cuántos días hacia atrás usar como histórico de referencia."
)

pb_hist = pb.tail(ventana_dias).copy()

# Percentiles para zonas
p25 = pb_hist["pb_prom_kwh"].quantile(0.25)
p50 = pb_hist["pb_prom_kwh"].quantile(0.50)
p75 = pb_hist["pb_prom_kwh"].quantile(0.75)

fig = go.Figure()

# Zona de oportunidad (P75+)
fig.add_hrect(y0=p75, y1=pb_hist["pb_prom_kwh"].max() * 1.1,
              fillcolor="#dcfce7", opacity=0.3, line_width=0,
              annotation_text="🟢 Zona de oportunidad (PB alta)",
              annotation_position="top left")

# Zona de esperar (P25-)
fig.add_hrect(y0=0, y1=p25,
              fillcolor="#fee2e2", opacity=0.3, line_width=0,
              annotation_text="🔴 Zona de esperar (PB baja)",
              annotation_position="bottom left")

# Líneas de percentil
for val, label, color, dash in [
    (p25, "P25", "#dc2626", "dot"),
    (p50, "Mediana", "#64748b", "dash"),
    (p75, "P75", "#16a34a", "dot"),
]:
    fig.add_hline(y=val, line_color=color, line_dash=dash, line_width=1.5,
                  annotation_text=f"{label}: ${val:,.0f}",
                  annotation_position="right")

# PB diaria
fig.add_scatter(
    x=pb_hist["fecha"], y=pb_hist["pb_prom_kwh"],
    mode="lines", name="PB diaria",
    line=dict(color="#2563eb", width=1.5),
    hovertemplate="%{x|%Y-%m-%d}<br>PB: $%{y:,.0f}/kWh<extra></extra>",
)

# Media móvil 30d
pb_hist["ma30"] = pb_hist["pb_prom_kwh"].rolling(30).mean()
fig.add_scatter(
    x=pb_hist["fecha"], y=pb_hist["ma30"],
    mode="lines", name="Media móvil 30d",
    line=dict(color="#f59e0b", width=2, dash="dash"),
)

# Marcar los procesos de compra sobre la gráfica
master_con_fecha = master[master["fecha_audiencia"].notna() & master["precio_adj_prom"].notna()].copy()
master_con_fecha = master_con_fecha[
    master_con_fecha["fecha_audiencia"] >= pb_hist["fecha"].min()
]
if len(master_con_fecha) > 0:
    fig.add_scatter(
        x=master_con_fecha["fecha_audiencia"],
        y=master_con_fecha["pb_prom_30d"],
        mode="markers",
        name="Proceso de compra",
        marker=dict(color="#7c3aed", size=9, symbol="diamond",
                    line=dict(color="white", width=1)),
        text=master_con_fecha["audiencia_id"],
        hovertemplate=(
            "<b>%{text}</b><br>Fecha: %{x|%Y-%m-%d}<br>"
            "PB 30d: $%{y:,.0f}/kWh<extra></extra>"
        ),
    )

# ── Pronóstico conectado al histórico ───────────────────────
if len(pronostico) > 0:
    # Arrancar desde la última fecha del histórico visible
    ultimo_hist = pb_hist["fecha"].max()
    pron_filt = pronostico[pronostico["fecha"] > ultimo_hist].copy()

    if "base_p50" in pron_filt.columns and len(pron_filt) > 0:
        # Banda de incertidumbre base p10-p90
        fig.add_scatter(
            x=list(pron_filt["fecha"]) + list(pron_filt["fecha"][::-1]),
            y=list(pron_filt["base_p90"]) + list(pron_filt["base_p10"][::-1]),
            fill="toself",
            fillcolor="rgba(124,58,237,0.10)",
            line=dict(color="rgba(0,0,0,0)"),
            name="Pronóstico base (P10-P90)",
            showlegend=True,
        )
        # Línea central base p50
        fig.add_scatter(
            x=pron_filt["fecha"], y=pron_filt["base_p50"],
            mode="lines", name="Pronóstico base (P50)",
            line=dict(color="#7c3aed", width=2, dash="dash"),
        )
        # Escenarios húmedo y seco (opcionales)
        if "humedo_mean" in pron_filt.columns:
            fig.add_scatter(
                x=pron_filt["fecha"], y=pron_filt["humedo_mean"],
                mode="lines", name="Escenario húmedo",
                line=dict(color="#0ea5e9", width=1.5, dash="dot"),
            )
        if "seco_mean" in pron_filt.columns:
            fig.add_scatter(
                x=pron_filt["fecha"], y=pron_filt["seco_mean"],
                mode="lines", name="Escenario seco",
                line=dict(color="#f97316", width=1.5, dash="dot"),
            )
        # Línea vertical en corte histórico / pronóstico
        fig.add_vline(
            x=str(ultimo_hist), line_dash="dot", line_color="#94a3b8", line_width=1.5,
            annotation_text="Hoy", annotation_position="top right",
        )

fig.update_layout(
    title="Precio de Bolsa histórico (TxF) con zonas de oportunidad y pronóstico",
    yaxis_title="$/kWh",
    xaxis_title="Fecha",
    height=480,
    plot_bgcolor="white",
    yaxis=dict(gridcolor="#f1f5f9"),
    legend=dict(orientation="h", yanchor="bottom", y=1.02),
)
st.plotly_chart(fig, use_container_width=True)

# ── Tabla de mejores y peores momentos históricos ────────────
st.markdown("---")
st.markdown("### 🗓️ ¿Qué pasó históricamente cuando se compró en PB alta vs baja?")

master_adj = master[master["precio_adj_prom"].notna() & master["pb_dia"].notna()].copy()

if len(master_adj) > 0:
    master_adj["zona_pb"] = pd.cut(
        master_adj["pb_relativa_90d"],
        bins=[0, 0.8, 1.1, 99],
        labels=["🔴 PB baja (<80% media)", "🟡 PB normal (80-110%)", "🟢 PB alta (>110% media)"]
    )

    resumen_zona = master_adj.groupby("zona_pb", observed=True).agg(
        n_procesos        = ("audiencia_id", "count"),
        precio_adj_prom   = ("precio_adj_prom", "mean"),
        spread_vs_pb_prom = ("spread_vs_pb_dia", "mean"),
        pb_dia_prom       = ("pb_dia", "mean"),
    ).round(1)

    col_z1, col_z2 = st.columns([1, 2])
    with col_z1:
        st.dataframe(
            resumen_zona.rename(columns={
                "n_procesos": "N° procesos",
                "precio_adj_prom": "Precio adj. prom.",
                "spread_vs_pb_prom": "Spread vs PB",
                "pb_dia_prom": "PB promedio",
            }),
            use_container_width=True,
        )
    with col_z2:
        fig_zona = go.Figure()
        for zona in resumen_zona.index:
            sub = master_adj[master_adj["zona_pb"] == zona]
            fig_zona.add_box(
                y=sub["spread_vs_pb_dia"],
                name=str(zona),
                boxmean=True,
            )
        fig_zona.add_hline(y=0, line_dash="dash", line_color="black")
        fig_zona.update_layout(
            title="Distribución del spread según zona de PB",
            yaxis_title="Spread $/kWh (adj - PB)",
            height=350,
            plot_bgcolor="white",
        )
        st.plotly_chart(fig_zona, use_container_width=True)

    st.markdown("""
    > **Conclusión clave:** Cuando la PB está alta (>110% de su media), el spread es más negativo
    > (los compradores pagan menos respecto a la PB), lo que confirma que **abrir procesos
    > en momentos de PB alta es históricamente ventajoso**.
    """)

# ── PB en tiempo real / próximos días ───────────────────────
st.markdown("---")
st.markdown("### 📊 Análisis de la última ventana (90 días)")

pb_90 = pb.tail(90).copy()

fig2 = go.Figure()
fig2.add_scatter(
    x=pb_90["fecha"], y=pb_90["pb_prom_kwh"],
    mode="lines+markers",
    line=dict(color="#2563eb", width=2),
    marker=dict(size=4),
    name="PB diaria",
    fill="tozeroy",
    fillcolor="rgba(37,99,235,0.07)",
)
fig2.add_scatter(
    x=pb_90["fecha"], y=pb_90["pb_max_kwh"],
    mode="lines", line=dict(color="#dc2626", width=1, dash="dot"),
    name="PB máxima del día",
)
fig2.add_scatter(
    x=pb_90["fecha"], y=pb_90["pb_min_kwh"],
    mode="lines", line=dict(color="#16a34a", width=1, dash="dot"),
    name="PB mínima del día",
    fill="tonexty",
    fillcolor="rgba(22,163,74,0.05)",
)
fig2.update_layout(
    title="PB — últimos 90 días (mín, promedio, máx diario)",
    yaxis_title="$/kWh",
    height=380,
    plot_bgcolor="white",
    yaxis=dict(gridcolor="#f1f5f9"),
)
st.plotly_chart(fig2, use_container_width=True)

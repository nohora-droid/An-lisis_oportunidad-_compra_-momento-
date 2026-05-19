# =============================================================
# Página 5: Proyección del Precio de Bolsa
# =============================================================

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(
    page_title="Proyección PB — BIA Energy",
    page_icon="🔮",
    layout="wide",
)

if "pb" not in st.session_state:
    st.warning("⚠️ Regresa a la página principal para cargar los datos.")
    st.stop()

pb     = st.session_state["pb"]
master = st.session_state["master"]

# Cargar pronóstico: primero desde session_state, si vacío carga directo del CSV
pronostico = st.session_state.get("pronostico", pd.DataFrame())
if len(pronostico) == 0:
    from scripts.data_loader import cargar_pronostico
    pronostico = cargar_pronostico()
    st.session_state["pronostico"] = pronostico  # guardar para próximas páginas

st.title("🔮 Proyección del Precio de Bolsa")
st.markdown("""
Pronóstico oficial de la PB diaria para los próximos meses, con tres escenarios hidrológicos:
**Base**, **Húmedo** (mayor disponibilidad hídrica) y **Seco** (menor disponibilidad hídrica).

> 💡 Usa esta proyección para anticipar el contexto de mercado al momento de la audiencia
> y comparar los precios ofertados contra la bolsa esperada.
""")
st.markdown("---")

if len(pronostico) == 0:
    st.error("No se encontró el archivo de pronóstico (`pronostico_pb_oficial.csv`). "
             "Verifica que esté en `data/raw/`.")
    st.stop()

# ── Parámetros de visualización ──────────────────────────────
col_c1, col_c2 = st.columns([2, 2])
with col_c1:
    dias_hist = st.slider(
        "Días de histórico a mostrar como contexto",
        min_value=90, max_value=730, value=365, step=30,
    )
with col_c2:
    mostrar_escenarios = st.multiselect(
        "Escenarios a mostrar",
        options=["Base P10-P90 (banda)", "Base P50", "Húmedo", "Seco"],
        default=["Base P10-P90 (banda)", "Base P50", "Húmedo", "Seco"],
    )

st.markdown("---")

# ── Gráfica principal: histórico + pronóstico ────────────────
st.markdown("### 📈 Histórico + Pronóstico de Precio de Bolsa")

pb_hist = pb.tail(dias_hist).copy()
fig = go.Figure()

# Histórico PB
fig.add_scatter(
    x=pb_hist["fecha"], y=pb_hist["pb_prom_kwh"],
    mode="lines", name="PB histórica (real)",
    line=dict(color="#2563eb", width=2),
    hovertemplate="%{x|%Y-%m-%d}<br>PB real: $%{y:,.0f}/kWh<extra></extra>",
)

# Media móvil 30d histórica
pb_hist["ma30"] = pb_hist["pb_prom_kwh"].rolling(30).mean()
fig.add_scatter(
    x=pb_hist["fecha"], y=pb_hist["ma30"],
    mode="lines", name="MM 30d (real)",
    line=dict(color="#f59e0b", width=1.5, dash="dash"),
)

# Pronóstico
ultimo_hist = pb_hist["fecha"].max()
pron = pronostico[pronostico["fecha"] > ultimo_hist].copy()

if len(pron) > 0:
    if "Base P10-P90 (banda)" in mostrar_escenarios and "base_p90" in pron.columns:
        fig.add_scatter(
            x=list(pron["fecha"]) + list(pron["fecha"][::-1]),
            y=list(pron["base_p90"]) + list(pron["base_p10"][::-1]),
            fill="toself",
            fillcolor="rgba(124,58,237,0.12)",
            line=dict(color="rgba(0,0,0,0)"),
            name="Base P10–P90",
            hoverinfo="skip",
        )

    if "Base P50" in mostrar_escenarios and "base_p50" in pron.columns:
        fig.add_scatter(
            x=pron["fecha"], y=pron["base_p50"],
            mode="lines", name="Base P50",
            line=dict(color="#7c3aed", width=2.5, dash="dash"),
            hovertemplate="%{x|%Y-%m-%d}<br>Base P50: $%{y:,.0f}/kWh<extra></extra>",
        )

    if "Húmedo" in mostrar_escenarios and "humedo_mean" in pron.columns:
        fig.add_scatter(
            x=pron["fecha"], y=pron["humedo_mean"],
            mode="lines", name="Húmedo",
            line=dict(color="#0ea5e9", width=1.8, dash="dot"),
            hovertemplate="%{x|%Y-%m-%d}<br>Húmedo: $%{y:,.0f}/kWh<extra></extra>",
        )

    if "Seco" in mostrar_escenarios and "seco_mean" in pron.columns:
        fig.add_scatter(
            x=pron["fecha"], y=pron["seco_mean"],
            mode="lines", name="Seco",
            line=dict(color="#f97316", width=1.8, dash="dot"),
            hovertemplate="%{x|%Y-%m-%d}<br>Seco: $%{y:,.0f}/kWh<extra></extra>",
        )

    # Línea divisoria histórico / pronóstico
    fig.add_vline(
        x=ultimo_hist,
        line_dash="dot", line_color="#94a3b8", line_width=1.5,
        annotation_text=f"Inicio pronóstico ({ultimo_hist.date()})",
        annotation_position="top left",
        annotation_font_size=11,
    )

fig.update_layout(
    title="Precio de Bolsa: histórico y pronóstico por escenario",
    yaxis_title="$/kWh",
    xaxis_title="Fecha",
    height=500,
    plot_bgcolor="white",
    yaxis=dict(gridcolor="#f1f5f9"),
    legend=dict(orientation="h", yanchor="bottom", y=1.02),
)
st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# ── Métricas de resumen del pronóstico ──────────────────────
st.markdown("### 📊 Resumen del período proyectado")

if len(pron) > 0 and "base_p50" in pron.columns:
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric(
            "Período proyectado",
            f"{pron['fecha'].min().strftime('%b %Y')} → {pron['fecha'].max().strftime('%b %Y')}"
        )
    with col2:
        pb_ult = pb["pb_prom_kwh"].iloc[-1]
        pron_ini = pron["base_p50"].iloc[0]
        delta_ini = pron_ini - pb_ult
        st.metric(
            "PB P50 inicio pronóstico",
            f"${pron_ini:,.0f}/kWh",
            delta=f"{delta_ini:+,.0f} vs actual",
        )
    with col3:
        pron_media = pron["base_p50"].mean()
        st.metric("PB P50 promedio período", f"${pron_media:,.0f}/kWh")
    with col4:
        pron_max = pron["base_p90"].max() if "base_p90" in pron.columns else None
        if pron_max:
            st.metric("Pico P90 esperado", f"${pron_max:,.0f}/kWh")
    with col5:
        pron_min = pron["base_p10"].min() if "base_p10" in pron.columns else None
        if pron_min:
            st.metric("Piso P10 esperado", f"${pron_min:,.0f}/kWh")

st.markdown("---")

# ── Vista mensual ────────────────────────────────────────────
st.markdown("### 📅 Promedio mensual del pronóstico")

if len(pron) > 0 and "base_p50" in pron.columns:
    pron["mes"] = pron["fecha"].dt.to_period("M").astype(str)

    cols_agg = {}
    if "base_p10" in pron.columns:  cols_agg["base_p10"] = ("base_p10", "mean")
    if "base_p50" in pron.columns:  cols_agg["base_p50"] = ("base_p50", "mean")
    if "base_p90" in pron.columns:  cols_agg["base_p90"] = ("base_p90", "mean")
    if "humedo_mean" in pron.columns: cols_agg["humedo_mean"] = ("humedo_mean", "mean")
    if "seco_mean" in pron.columns:   cols_agg["seco_mean"]   = ("seco_mean",   "mean")

    mensual = pron.groupby("mes").agg(**cols_agg).round(1)

    col_g, col_t = st.columns([3, 2])

    with col_g:
        fig2 = go.Figure()
        if "base_p90" in mensual.columns and "base_p10" in mensual.columns:
            fig2.add_scatter(
                x=list(mensual.index) + list(mensual.index[::-1]),
                y=list(mensual["base_p90"]) + list(mensual["base_p10"][::-1]),
                fill="toself",
                fillcolor="rgba(124,58,237,0.12)",
                line=dict(color="rgba(0,0,0,0)"),
                name="Base P10–P90",
                showlegend=True,
            )
        if "base_p50" in mensual.columns:
            fig2.add_scatter(
                x=mensual.index, y=mensual["base_p50"],
                mode="lines+markers+text",
                name="Base P50",
                line=dict(color="#7c3aed", width=2.5),
                marker=dict(size=8),
                text=[f"${v:,.0f}" for v in mensual["base_p50"]],
                textposition="top center",
            )
        if "humedo_mean" in mensual.columns:
            fig2.add_scatter(
                x=mensual.index, y=mensual["humedo_mean"],
                mode="lines+markers", name="Húmedo",
                line=dict(color="#0ea5e9", width=1.8, dash="dot"),
                marker=dict(size=6),
            )
        if "seco_mean" in mensual.columns:
            fig2.add_scatter(
                x=mensual.index, y=mensual["seco_mean"],
                mode="lines+markers", name="Seco",
                line=dict(color="#f97316", width=1.8, dash="dot"),
                marker=dict(size=6),
            )

        # Añadir últimas 3 medianas históricas como referencia
        ref_hist = (
            pb.assign(mes=pb["fecha"].dt.to_period("M").astype(str))
            .groupby("mes")["pb_prom_kwh"].mean()
            .tail(3)
        )
        fig2.add_scatter(
            x=ref_hist.index, y=ref_hist.values,
            mode="markers", name="Hist. reciente (ref.)",
            marker=dict(color="#64748b", size=8, symbol="x"),
        )

        fig2.update_layout(
            title="PB promedio mensual proyectada",
            yaxis_title="$/kWh",
            height=380,
            plot_bgcolor="white",
            yaxis=dict(gridcolor="#f1f5f9"),
        )
        st.plotly_chart(fig2, use_container_width=True)

    with col_t:
        rename_map = {
            "base_p10": "Base P10",
            "base_p50": "Base P50",
            "base_p90": "Base P90",
            "humedo_mean": "Húmedo",
            "seco_mean": "Seco",
        }
        st.dataframe(
            mensual.rename(columns=rename_map)
            .style.format("${:,.0f}")
            .background_gradient(subset=["Base P50"], cmap="YlOrRd"),
            use_container_width=True,
        )

st.markdown("---")

# ── Implicaciones para decisiones de compra ─────────────────
st.markdown("### 🎯 ¿Cómo usar el pronóstico en decisiones de compra?")

if len(pron) > 0 and "base_p50" in pron.columns:
    # ¿Cuándo se abren procesos activos? Cruzar con master
    master_abiertos = master[
        master["fecha_audiencia"] >= pd.Timestamp.now() - pd.Timedelta(days=30)
    ].copy() if len(master) > 0 else pd.DataFrame()

    # Comparar precio adj histórico vs PB proyectada
    pb_hist_prom = pb.tail(90)["pb_prom_kwh"].mean()
    pron_p50_prom = pron["base_p50"].mean()
    spread_esperado = pron_p50_prom - pb_hist_prom

    col_i1, col_i2 = st.columns(2)

    with col_i1:
        direction = "📈 subir" if spread_esperado > 0 else "📉 bajar"
        st.info(
            f"**PB proyectada (P50 prom.):** ${pron_p50_prom:,.0f}/kWh  \n"
            f"**PB histórica reciente (90d):** ${pb_hist_prom:,.0f}/kWh  \n"
            f"**Diferencia:** {spread_esperado:+,.0f} $/kWh → se espera que la PB **{direction}**"
        )

        if pron_p50_prom > pb_hist_prom * 1.05:
            st.success(
                "✅ **Señal positiva:** La bolsa proyectada es mayor a la actual. "
                "Los generadores tendrán incentivo para contratar a largo plazo "
                "a precios por debajo de la bolsa esperada."
            )
        elif pron_p50_prom < pb_hist_prom * 0.95:
            st.warning(
                "⚠️ **Señal de cautela:** La bolsa proyectada es menor a la actual. "
                "Los generadores pueden exigir primas más altas. "
                "Evalúa si aplazar el proceso mejora las condiciones."
            )
        else:
            st.info(
                "ℹ️ **Mercado estable:** La PB proyectada no difiere significativamente "
                "de la actual. El timing es neutral."
            )

    with col_i2:
        # Meses del pronóstico vs meses históricamente buenos para contratar
        meses_buenos = [9, 10, 11]  # Sep-Nov históricamente mejor spread
        pron["mes_num"] = pron["fecha"].dt.month
        ventanas = pron[pron["mes_num"].isin(meses_buenos)][["fecha", "base_p50"]]

        if len(ventanas) > 0:
            st.markdown("**Ventanas proyectadas en meses históricamente favorables (Sep-Nov):**")
            ventanas_mes = (
                ventanas.groupby(ventanas["fecha"].dt.to_period("M").astype(str))["base_p50"]
                .mean().round(0)
            )
            for mes, val in ventanas_mes.items():
                st.markdown(f"- **{mes}**: PB base P50 esperada **${val:,.0f}/kWh**")
        else:
            st.markdown(
                "No hay meses Sep-Nov en el período proyectado. "
                "Consulta el histórico para referencia de timing."
            )

st.markdown("---")

# ── Tabla completa del pronóstico ───────────────────────────
with st.expander("📋 Ver tabla completa del pronóstico (datos diarios)", expanded=False):
    if len(pronostico) > 0:
        df_show = pronostico.copy()
        df_show["fecha"] = df_show["fecha"].dt.strftime("%Y-%m-%d")
        rename = {
            "base_p10": "Base P10",
            "base_p50": "Base P50",
            "base_p90": "Base P90",
            "humedo_mean": "Húmedo",
            "seco_mean": "Seco",
        }
        st.dataframe(
            df_show.rename(columns=rename).style.format(
                {k: "${:,.0f}" for k in rename.values() if k != "fecha"}
            ),
            use_container_width=True,
            height=400,
        )

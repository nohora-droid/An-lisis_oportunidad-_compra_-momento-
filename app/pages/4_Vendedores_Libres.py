# =============================================================
# Página 4: Vendedores Libres — Agentes no adjudicados
# =============================================================

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from scripts.analisis import alertas_vendedores_libres

st.set_page_config(page_title="Vendedores Libres — BIA Energy", page_icon="📋", layout="wide")

if "ofertas" not in st.session_state:
    st.warning("⚠️ Regresa a la página principal para cargar los datos.")
    st.stop()

ofertas = st.session_state["ofertas"]
master  = st.session_state["master"]

st.title("📋 Vendedores Libres — Oportunidades de Contacto Directo")
st.markdown("""
Agentes que **ofertaron pero no fueron adjudicados** en procesos recientes.

> 💡 Un generador no adjudicado tiene energía disponible y puede estar abierto a negociaciones
> bilaterales. Esta página te ayuda a identificarlos y priorizarlos.
""")
st.markdown("---")

# ── Fecha de corte de los datos ──────────────────────────────
fecha_corte_datos = pd.to_datetime(master["fecha_audiencia"]).max()
fecha_mas_antigua = pd.to_datetime(master["fecha_audiencia"]).min()

# Banner de contexto temporal — siempre visible
# Gap entre corte de ofertas y corte de master
fecha_corte_ofertas = pd.to_datetime(ofertas["fecha_audiencia"]).max()
dias_gap = (fecha_corte_datos - fecha_corte_ofertas).days

col_banner1, col_banner2 = st.columns([3, 2])
with col_banner1:
    st.info(
        f"📅 **Corte de datos de ofertas:** **{fecha_corte_ofertas.strftime('%d de %B de %Y')}** · "
        f"Histórico: {fecha_mas_antigua.strftime('%b %Y')} → {fecha_corte_ofertas.strftime('%b %Y')}\n\n"
        f"Los 'últimos N días' se cuentan desde esa fecha, no desde hoy."
    )
with col_banner2:
    if dias_gap > 30:
        st.warning(
            f"⚠️ **{dias_gap} días sin actualizar**\n\n"
            f"Hay audiencias realizadas entre **{fecha_corte_ofertas.strftime('%d/%m/%Y')}** "
            f"y **{fecha_corte_datos.strftime('%d/%m/%Y')}** que no están en el archivo de ofertas. "
            f"Para verlas, actualiza `ofertas_por_agente_detalle.csv` con los datos de SICEP."
        )

# ── Configuración ────────────────────────────────────────────
col_c1, col_c2, col_c3 = st.columns(3)
with col_c1:
    dias_ventana = st.number_input(
        "Ventana de seguimiento (días)", min_value=30, max_value=365, value=90,
        help="Buscar vendedores no adj. en los últimos N días contados desde el corte del archivo."
    )
with col_c2:
    max_precio = st.number_input(
        "Precio máximo a considerar ($/kWh)", min_value=100, max_value=1000, value=500,
        help="Filtrar agentes con precio promedio por debajo de este valor."
    )
with col_c3:
    tipo_curva_sel = st.multiselect(
        "Tipo de curva",
        options=ofertas["tipo_curva"].dropna().unique().tolist() if "tipo_curva" in ofertas.columns else ["PLANO"],
        default=ofertas["tipo_curva"].dropna().unique().tolist() if "tipo_curva" in ofertas.columns else ["PLANO"],
    )

# Mostrar rango exacto que se está consultando
fecha_desde_ventana = fecha_corte_datos - pd.Timedelta(days=int(dias_ventana))
st.caption(
    f"🔍 Buscando audiencias entre **{fecha_desde_ventana.strftime('%d/%m/%Y')}** "
    f"y **{fecha_corte_datos.strftime('%d/%m/%Y')}** "
    f"({int(dias_ventana)} días · año{'s' if fecha_desde_ventana.year != fecha_corte_datos.year else ''}: "
    f"{'%d–%d' % (fecha_desde_ventana.year, fecha_corte_datos.year) if fecha_desde_ventana.year != fecha_corte_datos.year else str(fecha_corte_datos.year)})"
)

# ── Tabla de vendedores libres ───────────────────────────────
libres = alertas_vendedores_libres(ofertas, master, dias_ventana=int(dias_ventana))

if len(libres) == 0:
    st.warning(
        f"No se encontraron agentes no adjudicados entre "
        f"**{fecha_desde_ventana.strftime('%d/%m/%Y')}** y "
        f"**{fecha_corte_datos.strftime('%d/%m/%Y')}**. "
        f"Prueba ampliar la ventana de seguimiento."
    )
else:
    # Aplicar filtro de precio
    libres_filt = libres[libres["precio_prom"] <= max_precio]

    st.markdown(f"### 🎯 {len(libres_filt)} agentes con energía disponible (últimos {dias_ventana}d)")

    col_m1, col_m2, col_m3 = st.columns(3)
    with col_m1:
        st.metric("Agentes identificados", len(libres_filt))
    with col_m2:
        if len(libres_filt) > 0:
            st.metric("Precio mín. disponible", f"${libres_filt['precio_min'].min():,.0f}/kWh")
    with col_m3:
        if len(libres_filt) > 0:
            st.metric("Precio prom. disponible", f"${libres_filt['precio_prom'].mean():,.0f}/kWh")

    # Tabla principal
    df_display = libres_filt.reset_index().rename(columns={
        "agente_nombre":   "Agente",
        "veces_no_adj":    "Ofertas disponibles",
        "tipo":            "Situación",
        "años_vigencia":   "Años vigencia",
        "procesos":        "Últimos procesos",
        "precio_prom":     "Precio prom. $/kWh",
        "precio_min":      "Precio mín. $/kWh",
        "ultima_audiencia":"Última audiencia",
        "horizonte_dias":  "Horizonte días",
    })
    if "Última audiencia" in df_display.columns:
        df_display["Última audiencia"] = pd.to_datetime(
            df_display["Última audiencia"]).dt.strftime("%d/%m/%Y")

    cols_show = [c for c in [
        "Agente", "Situación", "Años vigencia", "Ofertas disponibles",
        "Precio prom. $/kWh", "Precio mín. $/kWh",
        "Últimos procesos", "Última audiencia", "Horizonte días"
    ] if c in df_display.columns]

    st.dataframe(
        df_display[cols_show].style.background_gradient(
            subset=["Precio prom. $/kWh"], cmap="RdYlGn_r"
        ),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("---")

    # ── Gráfica de precio vs horizonte ──────────────────────
    st.markdown("### 📊 Precio vs horizonte de anticipación")
    fig = go.Figure()
    fig.add_scatter(
        x=libres_filt["horizonte_dias"],
        y=libres_filt["precio_prom"],
        mode="markers+text",
        marker=dict(
            size=libres_filt["veces_no_adj"] * 8,
            color=libres_filt["precio_prom"],
            colorscale="RdYlGn_r",
            showscale=True,
            colorbar=dict(title="Precio $/kWh"),
        ),
        text=libres_filt.index.str.split().str[0],
        textposition="top center",
        hovertemplate=(
            "<b>%{text}</b><br>"
            "Precio prom: $%{y:,.0f}/kWh<br>"
            "Horizonte: %{x:.0f} días<extra></extra>"
        ),
    )
    fig.update_layout(
        title="Precio promedio vs Horizonte de anticipación (tamaño = frecuencia no adj.)",
        xaxis_title="Horizonte de anticipación (días)",
        yaxis_title="Precio promedio ofertado ($/kWh)",
        height=420,
        plot_bgcolor="white",
        yaxis=dict(gridcolor="#f1f5f9"),
        xaxis=dict(gridcolor="#f1f5f9"),
    )
    st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# ── Detalle de un proceso reciente ───────────────────────────
st.markdown("### 🔍 Detalle de un proceso reciente")
st.caption(
    f"Mostrando procesos entre **{fecha_desde_ventana.strftime('%d/%m/%Y')}** "
    f"y **{fecha_corte_datos.strftime('%d/%m/%Y')}** — "
    f"{int(dias_ventana)} días hacia atrás desde el corte de datos"
)

fecha_corte = master["fecha_audiencia"].max() - pd.Timedelta(days=int(dias_ventana))
procesos_rec = master[master["fecha_audiencia"] >= fecha_corte].sort_values(
    "fecha_audiencia", ascending=False
)

if len(procesos_rec) > 0:
    proceso_sel = st.selectbox(
        "Selecciona un proceso",
        options=procesos_rec["audiencia_id"].tolist(),
        format_func=lambda x: (
            f"{x} — "
            f"{procesos_rec[procesos_rec['audiencia_id']==x]['fecha_audiencia'].dt.strftime('%d/%m/%Y').values[0]}"
        )
    )

    # Ofertas de ese proceso
    ofertas_proc = ofertas[ofertas["audiencia_id"] == proceso_sel].copy()

    if len(ofertas_proc) > 0:
        st.markdown(f"**{len(ofertas_proc)} ofertas en `{proceso_sel}`**")

        info_proc = procesos_rec[procesos_rec["audiencia_id"] == proceso_sel].iloc[0]
        col_p1, col_p2, col_p3, col_p4 = st.columns(4)
        with col_p1:
            st.metric("Comprador", info_proc.get("comprador", "N/D"))
        with col_p2:
            st.metric("Fecha audiencia", str(info_proc["fecha_audiencia"].date()))
        with col_p3:
            adj_precio = info_proc.get("precio_adj_prom")
            st.metric("Precio adj.", f"${adj_precio:,.0f}/kWh" if pd.notna(adj_precio) else "Pendiente")
        with col_p4:
            pb_30 = info_proc.get("pb_prom_30d")
            st.metric("PB 30d", f"${pb_30:,.0f}/kWh" if pd.notna(pb_30) else "N/D")

        # Tabla de ofertas del proceso
        cols_show = ["agente_nombre", "precio_oferta", "cantidad_ofertada",
                     "adjudicada", "pct_adjudicado", "tipo_curva"]
        cols_exist = [c for c in cols_show if c in ofertas_proc.columns]
        df_proc = ofertas_proc[cols_exist].copy()
        df_proc = df_proc.sort_values("precio_oferta")

        def highlight_adj(row):
            if row.get("adjudicada", False):
                return ["background-color: #dcfce7"] * len(row)
            return [""] * len(row)

        st.dataframe(
            df_proc.style.apply(highlight_adj, axis=1),
            use_container_width=True,
            hide_index=True,
        )

        # Gráfica de barras de precios
        fig_pr = go.Figure()
        fig_pr.add_bar(
            x=df_proc["agente_nombre"].str.split().str[0],
            y=df_proc["precio_oferta"],
            marker_color=df_proc["adjudicada"].map(
                {True: "#16a34a", False: "#dc2626"}
            ),
            text=df_proc["precio_oferta"].map("${:,.0f}".format),
            textposition="outside",
        )
        if pd.notna(adj_precio):
            fig_pr.add_hline(
                y=adj_precio, line_dash="dash", line_color="#7c3aed",
                annotation_text=f"Precio adj: ${adj_precio:,.0f}",
                annotation_position="right",
            )
        fig_pr.update_layout(
            title=f"Precios ofertados en {proceso_sel} (🟢 adj. / 🔴 no adj.)",
            yaxis_title="$/kWh",
            height=350,
            plot_bgcolor="white",
            yaxis=dict(gridcolor="#f1f5f9"),
        )
        st.plotly_chart(fig_pr, use_container_width=True)
    else:
        st.info("Sin ofertas registradas para este proceso.")

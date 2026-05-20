# =============================================================
# Página 2: Análisis de Agentes / Generadores
# =============================================================

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from scripts.analisis import perfil_agentes, estacionalidad_agente, historial_agente
from scripts.indexador_ipp import indexar_ofertas, meses_disponibles, resumen_indexacion

st.set_page_config(page_title="Agentes — BIA Energy", page_icon="🤝", layout="wide")

if "ofertas" not in st.session_state:
    st.warning("⚠️ Regresa a la página principal para cargar los datos.")
    st.stop()

pb               = st.session_state["pb"]
ofertas_full     = st.session_state["ofertas"]
master           = st.session_state["master"]
ipp              = st.session_state["ipp"]
mes_idx_global   = st.session_state.get("mes_idx_global")
ipp_valor_global = st.session_state.get("ipp_valor_global")
audiencias_sel   = st.session_state.get("audiencias_sel", ofertas_full["audiencia_id"].unique().tolist())

# Aplicar filtro de audiencias
ofertas = ofertas_full[ofertas_full["audiencia_id"].isin(audiencias_sel)].copy()

st.title("🤝 Análisis por Agente / Generador")
st.markdown("""
Perfil detallado de cada agente: cuándo ofertan, a qué precios, con qué horizonte
de anticipación y qué tan probable es que sean adjudicados.
""")
st.markdown("---")

# ── Indexación de precios (usa selector global del sidebar) ──
tiene_ipp = any(c.lower() == "ipp" for c in ofertas.columns)
mes_idx   = mes_idx_global  # viene del sidebar

# Banner informativo con IPP activo
col_bx1, col_bx2 = st.columns([3, 2])
with col_bx1:
    if mes_idx and ipp_valor_global:
        st.info(f"📌 Indexando a **{mes_idx}** · IPP = **{ipp_valor_global:.2f}** "
                f"· {len(audiencias_sel)} audiencias seleccionadas  \n"
                f"_(Cambia el mes y las audiencias en el **sidebar izquierdo**)_")
    else:
        st.info("⚙️ Selecciona el mes de indexación en el **sidebar izquierdo**.")
with col_bx2:
    if not tiene_ipp:
        st.warning("⚠️ Sin columna IPP en el archivo actual — precios sin indexar.")

# Aplicar indexación
if tiene_ipp and mes_idx:
    ofertas_idx, col_precio = indexar_ofertas(ofertas, ipp, mes_idx)
    if col_precio == "precio_oferta":
        label_precio = "Precio oferta ($/kWh, sin indexar)"
    else:
        label_precio = f"Precio indexado a {mes_idx} ($/kWh)"
        res = resumen_indexacion(ofertas_idx, "precio_oferta", col_precio)
        st.caption(
            f"Indexadas: {res['n_indexados']} · Sin IPP: {res['n_sin_ipp']} · "
            f"Factor prom: {res['factor_promedio']} · "
            f"Precio prom: ${res['precio_orig_prom']:,.0f} → ${res['precio_idx_prom']:,.0f}"
        )
else:
    ofertas_idx = ofertas.copy()
    col_precio  = "precio_oferta"
    label_precio = "Precio oferta ($/kWh, sin indexar)"

# ── Tabla resumen de agentes ─────────────────────────────────
perfil = perfil_agentes(ofertas_idx.rename(columns={"precio_idx": "precio_oferta_work"}),
                         pb, min_ofertas=3)

# Recalcular con la columna indexada
perfil2 = ofertas_idx.groupby("agente_nombre").agg(
    n_ofertas           = ("audiencia_id", "count"),
    tasa_adj_pct        = ("adjudicada", lambda x: round(x.mean() * 100, 1)),
    precio_prom         = (col_precio, "mean"),
    precio_min          = (col_precio, "min"),
    precio_max          = (col_precio, "max"),
    horizonte_dias_prom = ("horizonte_dias", "mean"),
    vigencia_años_prom  = ("vigencia_años", "mean"),
    primera_oferta      = ("fecha_audiencia", "min"),
    ultima_oferta       = ("fecha_audiencia", "max"),
).round(2)
perfil2 = perfil2[perfil2["n_ofertas"] >= 3].sort_values("n_ofertas", ascending=False)

st.markdown("### 📋 Resumen por Agente")

# Filtros de tabla
col_f1, col_f2 = st.columns([2, 2])
with col_f1:
    busq = st.text_input("🔍 Buscar agente", "")
with col_f2:
    min_adj = st.slider("Tasa mínima de adjudicación (%)", 0, 100, 0)

df_tabla = perfil2.copy()
if busq:
    df_tabla = df_tabla[df_tabla.index.str.upper().str.contains(busq.upper())]
if min_adj > 0:
    df_tabla = df_tabla[df_tabla["tasa_adj_pct"] >= min_adj]

# Colorear tasa de adjudicación
def color_adj(val):
    if val >= 70:
        return "background-color: #dcfce7"
    elif val >= 30:
        return "background-color: #fef9c3"
    else:
        return "background-color: #fee2e2"

st.dataframe(
    df_tabla.rename(columns={
        "n_ofertas": "N° ofertas",
        "tasa_adj_pct": "Tasa adj. %",
        "precio_prom": "Precio prom.",
        "precio_min": "Precio mín.",
        "precio_max": "Precio máx.",
        "horizonte_dias_prom": "Horizonte días",
        "vigencia_años_prom": "Vigencia años",
        "primera_oferta": "Primera oferta",
        "ultima_oferta": "Última oferta",
    }).style.map(color_adj, subset=["Tasa adj. %"]),
    use_container_width=True,
    height=400,
)

st.markdown("---")

# ── Perfil individual de un agente ──────────────────────────
st.markdown("### 🔍 Perfil individual")

agentes_lista = sorted(ofertas["agente_nombre"].unique().tolist())
agente_sel = st.selectbox("Selecciona un agente", agentes_lista)

hist_ag = historial_agente(ofertas_idx, agente_sel)
est_ag  = estacionalidad_agente(ofertas_idx, agente_sel)

col1, col2, col3, col4 = st.columns(4)
sub_ag = ofertas_idx[ofertas_idx["agente_nombre"] == agente_sel]
with col1:
    st.metric("Total de ofertas", len(sub_ag))
with col2:
    tasa = sub_ag["adjudicada"].mean()
    st.metric("Tasa de adjudicación", f"{tasa*100:.1f}%")
with col3:
    precio_m = sub_ag[col_precio].mean()
    st.metric(f"Precio promedio", f"${precio_m:,.0f}/kWh")
with col4:
    hor = sub_ag["horizonte_dias"].mean()
    st.metric("Horizonte promedio", f"{hor:.0f} días")

tab_a, tab_b, tab_c = st.tabs(["📅 Estacionalidad", "📊 Distribución de precios", "📋 Historial"])

with tab_a:
    col_ea, col_eb = st.columns(2)
    with col_ea:
        if len(est_ag) > 0:
            fig_est = go.Figure()
            fig_est.add_bar(
                x=est_ag.index,
                y=est_ag.values,
                marker_color="#2563eb",
                text=est_ag.values,
                textposition="outside",
            )
            fig_est.update_layout(
                title=f"Meses en que {agente_sel.split()[0]} suele ofertar",
                yaxis_title="Número de ofertas",
                height=320,
                plot_bgcolor="white",
                yaxis=dict(gridcolor="#f1f5f9"),
            )
            st.plotly_chart(fig_est, use_container_width=True)

    with col_eb:
        # Horizonte de anticipación
        hor_data = sub_ag["horizonte_dias"].dropna()
        if len(hor_data) > 0:
            fig_hor = go.Figure()
            fig_hor.add_histogram(
                x=hor_data,
                nbinsx=15,
                marker_color="#16a34a",
                opacity=0.8,
            )
            fig_hor.add_vline(
                x=float(hor_data.mean()), line_dash="dash", line_color="red",
                annotation_text=f"Prom: {hor_data.mean():.0f}d",
                annotation_position="top right",
            )
            fig_hor.update_layout(
                title="Distribución del horizonte de anticipación",
                xaxis_title="Días entre audiencia e inicio vigencia",
                height=320,
                plot_bgcolor="white",
                yaxis=dict(gridcolor="#f1f5f9"),
            )
            st.plotly_chart(fig_hor, use_container_width=True)

with tab_b:
    precios_ag = sub_ag[col_precio].dropna()
    if len(precios_ag) > 0:
        fig_pr = go.Figure()
        # Box por adjudicación
        for adj_val, label, color in [(True, "Adjudicadas", "#16a34a"), (False, "No adjudicadas", "#dc2626")]:
            subset = sub_ag[sub_ag["adjudicada"] == adj_val][col_precio].dropna()
            if len(subset) > 0:
                fig_pr.add_box(
                    y=subset, name=label,
                    marker_color=color, boxmean=True,
                )
        fig_pr.update_layout(
            title=f"Distribución de precios ofertados — {label_precio}",
            yaxis_title="$/kWh",
            height=380,
            plot_bgcolor="white",
        )
        st.plotly_chart(fig_pr, use_container_width=True)

        # Evolución de precios en el tiempo
        fig_ev = go.Figure()
        sub_sorted = sub_ag.sort_values("fecha_audiencia")
        fig_ev.add_scatter(
            x=sub_sorted["fecha_audiencia"],
            y=sub_sorted[col_precio],
            mode="markers",
            marker=dict(
                color=sub_sorted["adjudicada"].map({True: "#16a34a", False: "#dc2626"}),
                size=9, opacity=0.8,
            ),
            text=sub_sorted["audiencia_id"],
            hovertemplate="<b>%{text}</b><br>Precio: %{y:,.0f} $/kWh<extra></extra>",
        )
        # Añadir PB del día para comparación
        pb_filt = pb[["fecha", "pb_prom_kwh"]].copy()
        pb_filt = pb_filt[
            (pb_filt["fecha"] >= sub_ag["fecha_audiencia"].min()) &
            (pb_filt["fecha"] <= sub_ag["fecha_audiencia"].max())
        ]
        fig_ev.add_scatter(
            x=pb_filt["fecha"], y=pb_filt["pb_prom_kwh"],
            mode="lines", name="PB diaria",
            line=dict(color="#94a3b8", width=1.5, dash="dot"),
        )
        fig_ev.update_layout(
            title="Evolución de precios ofertados vs PB (🟢 adj. / 🔴 no adj.)",
            yaxis_title="$/kWh",
            height=350,
            plot_bgcolor="white",
            yaxis=dict(gridcolor="#f1f5f9"),
        )
        st.plotly_chart(fig_ev, use_container_width=True)

with tab_c:
    if len(hist_ag) > 0:
        for col in ["fecha_audiencia", "vigencia_inicio", "vigencia_fin"]:
            if col in hist_ag.columns:
                hist_ag[col] = pd.to_datetime(hist_ag[col]).dt.strftime("%Y-%m-%d")
        st.dataframe(hist_ag, use_container_width=True, hide_index=True)
    else:
        st.info("Sin historial disponible para este agente.")

st.markdown("---")

# ── Comparación de agentes ───────────────────────────────────
st.markdown("### ⚡ Comparar agentes")
agentes_comp = st.multiselect(
    "Selecciona agentes para comparar",
    options=agentes_lista,
    default=agentes_lista[:5] if len(agentes_lista) >= 5 else agentes_lista,
)

if agentes_comp:
    df_comp = ofertas_idx[ofertas_idx["agente_nombre"].isin(agentes_comp)]
    fig_comp = go.Figure()
    for ag in agentes_comp:
        sub = df_comp[df_comp["agente_nombre"] == ag][col_precio].dropna()
        if len(sub) > 0:
            fig_comp.add_box(y=sub, name=ag.split()[0], boxmean=True)
    fig_comp.update_layout(
        title=f"Comparación de precios ofertados ({label_precio})",
        yaxis_title="$/kWh",
        height=420,
        plot_bgcolor="white",
    )
    st.plotly_chart(fig_comp, use_container_width=True)

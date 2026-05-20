# =============================================================
# Página 6: Precios por Año de Vigencia
# =============================================================
"""
Muestra el precio ofertado vs adjudicado agrupado por el año/mes
al que aplica la energía contratada (período de vigencia).
Indexa todos los precios al IPP global seleccionado en el sidebar.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from scripts.indexador_ipp import indexar_ofertas, resumen_indexacion

st.set_page_config(
    page_title="Precios por Vigencia — BIA Energy",
    page_icon="📆",
    layout="wide",
)

if "ofertas" not in st.session_state:
    st.warning("⚠️ Regresa a la página principal para cargar los datos.")
    st.stop()

ofertas_full     = st.session_state["ofertas"]
ipp              = st.session_state["ipp"]
mes_idx          = st.session_state.get("mes_idx_global")
ipp_valor        = st.session_state.get("ipp_valor_global")
audiencias_sel   = st.session_state.get("audiencias_sel",
                       ofertas_full["audiencia_id"].unique().tolist())

# ── Header ───────────────────────────────────────────────────
st.title("📆 Precios por Año de Vigencia")

ipp_label = (f"Indexado a **{mes_idx}** · IPP {ipp_valor:.2f}"
             if mes_idx and ipp_valor else "Sin indexar")
st.caption(f"{ipp_label} · _(Cambia el mes de indexación en el sidebar)_")
st.markdown("---")

# ── Filtro de período de audiencias ─────────────────────────
OPCIONES_PERIODO = {
    "Todas las audiencias":  None,
    "Último mes":            1,
    "Últimos 3 meses":       3,
    "Últimos 6 meses":       6,
    "Último año":            12,
    "Últimos 2 años":        24,
    "Últimos 3 años":        36,
    "Rango personalizado":  "custom",
}

col_p1, col_p2 = st.columns([2, 3])
with col_p1:
    periodo_sel = st.selectbox(
        "📅 Período de audiencias a incluir",
        options=list(OPCIONES_PERIODO.keys()),
        index=0,
        help="Filtra las audiencias por fecha en que se realizaron, "
             "independientemente del año de vigencia del contrato.",
    )

fecha_max_aud = pd.to_datetime(ofertas_full["fecha_audiencia"]).max()

if OPCIONES_PERIODO[periodo_sel] is None:
    fecha_desde = None
    fecha_hasta = None
elif OPCIONES_PERIODO[periodo_sel] == "custom":
    with col_p2:
        rango_custom = st.date_input(
            "Rango de fechas",
            value=(
                (fecha_max_aud - pd.DateOffset(months=6)).date(),
                fecha_max_aud.date(),
            ),
            key="rango_custom_vigencia",
        )
    if isinstance(rango_custom, (list, tuple)) and len(rango_custom) == 2:
        fecha_desde = pd.Timestamp(rango_custom[0])
        fecha_hasta = pd.Timestamp(rango_custom[1])
    else:
        fecha_desde = fecha_hasta = None
else:
    meses_atras = OPCIONES_PERIODO[periodo_sel]
    fecha_hasta = fecha_max_aud
    fecha_desde = fecha_max_aud - pd.DateOffset(months=meses_atras)

# Aplicar filtro de período + filtro de audiencias del sidebar
mask_aud = ofertas_full["audiencia_id"].isin(audiencias_sel)
if fecha_desde is not None:
    fechas_aud = pd.to_datetime(ofertas_full["fecha_audiencia"])
    mask_periodo = (fechas_aud >= fecha_desde) & (fechas_aud <= fecha_hasta)
    mask_final = mask_aud & mask_periodo
else:
    mask_final = mask_aud

ofertas_base = ofertas_full[mask_final].copy()

# Mostrar info de qué quedó
n_aud_filt = ofertas_base["audiencia_id"].nunique()
n_aud_total = ofertas_full["audiencia_id"].nunique()
with col_p2:
    if OPCIONES_PERIODO[periodo_sel] != "custom":
        fecha_info = (
            f"desde **{fecha_desde.strftime('%d/%m/%Y')}** hasta **{fecha_hasta.strftime('%d/%m/%Y')}**"
            if fecha_desde else "todo el histórico"
        )
        if n_aud_filt == 0:
            st.error(f"⚠️ Sin audiencias en ese período.")
        else:
            st.success(
                f"✅ **{n_aud_filt}** audiencias ({fecha_info})  \n"
                f"{len(ofertas_base):,} ofertas incluidas"
            )

if len(ofertas_base) == 0:
    st.warning("No hay datos para el período seleccionado. Amplía el rango.")
    st.stop()

st.markdown("---")

# ── Indexar precios ──────────────────────────────────────────
tiene_ipp = any(c.lower() == "ipp" for c in ofertas_base.columns)

if tiene_ipp and mes_idx:
    ofertas_idx, col_precio = indexar_ofertas(ofertas_base, ipp, mes_idx)
    sufijo_ind = " ind."
else:
    ofertas_idx = ofertas_base.copy()
    col_precio  = "precio_oferta"
    sufijo_ind  = ""

# ── Expandir ofertas mes a mes por vigencia ──────────────────
filas = []
for _, row in ofertas_idx.iterrows():
    vi = row.get("vigencia_inicio")
    vf = row.get("vigencia_fin")
    if pd.isnull(vi) or pd.isnull(vf):
        continue
    precio = row.get(col_precio)
    if pd.isnull(precio):
        continue
    adj = bool(row.get("adjudicada", False))
    for mes_dt in pd.date_range(vi, vf, freq="MS"):
        filas.append({
            "año":           mes_dt.year,
            "mes_num":       mes_dt.month,
            "mes_label":     mes_dt.strftime("%b"),
            "precio_oferta": precio,
            "precio_adj":    precio if adj else np.nan,
            "adjudicada":    adj,
            "agente":        row.get("agente_nombre", ""),
            "audiencia_id":  row.get("audiencia_id", ""),
        })

if not filas:
    st.warning("No hay datos con vigencia definida para las audiencias seleccionadas.")
    st.stop()

df_exp = pd.DataFrame(filas)

# ── Filtro por rango de años de vigencia ─────────────────────
años_disp = sorted(df_exp["año"].unique().tolist())
col_f1, col_f2 = st.columns([2, 3])
with col_f1:
    año_rango = st.select_slider(
        "Rango de años de vigencia",
        options=años_disp,
        value=(min(años_disp), max(años_disp)),
    )
with col_f2:
    vista = st.radio("Vista", ["Anual", "Mensual"], horizontal=True)

df_filt = df_exp[
    (df_exp["año"] >= año_rango[0]) & (df_exp["año"] <= año_rango[1])
].copy()

# ── Agrupaciones ─────────────────────────────────────────────
anual = (
    df_filt.groupby("año")
    .agg(
        precio_oferta = ("precio_oferta", "mean"),
        precio_adj    = ("precio_adj",    "mean"),
        n_ofertas     = ("precio_oferta", "count"),
        n_adj         = ("adjudicada",    "sum"),
    )
    .round(2)
    .reset_index()
)
anual["diferencia"] = (anual["precio_adj"] - anual["precio_oferta"]).round(2)

# ── Métricas rápidas ─────────────────────────────────────────
if len(anual) > 0:
    año_ini = anual.iloc[0]
    año_fin = anual.iloc[-1]
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    with col_m1:
        st.metric(f"Oferta prom. {int(año_ini['año'])}",
                  f"${año_ini['precio_oferta']:,.2f}")
    with col_m2:
        st.metric(f"Adj. prom. {int(año_ini['año'])}",
                  f"${año_ini['precio_adj']:,.2f}" if pd.notna(año_ini['precio_adj']) else "N/D")
    with col_m3:
        st.metric(f"Oferta prom. {int(año_fin['año'])}",
                  f"${año_fin['precio_oferta']:,.2f}")
    with col_m4:
        st.metric(f"Adj. prom. {int(año_fin['año'])}",
                  f"${año_fin['precio_adj']:,.2f}" if pd.notna(año_fin['precio_adj']) else "N/D")

st.markdown("---")

# ══════════════════════════════════════════════════════════════
#  VISTA ANUAL
# ══════════════════════════════════════════════════════════════
if vista == "Anual":
    col_g, col_t = st.columns([3, 2])

    with col_g:
        fig = go.Figure()

        # Barras oferta
        fig.add_bar(
            x=anual["año"].astype(str),
            y=anual["precio_oferta"],
            name="Precio oferta",
            marker_color="#3b82f6",
            text=[f"${v:,.2f}" for v in anual["precio_oferta"]],
            textposition="outside",
        )

        # Barras adjudicado (solo filas con dato)
        adj_validas = anual[anual["precio_adj"].notna()]
        if len(adj_validas) > 0:
            fig.add_bar(
                x=adj_validas["año"].astype(str),
                y=adj_validas["precio_adj"],
                name="Precio adjudicado",
                marker_color="#22c55e",
                text=[f"${v:,.2f}" for v in adj_validas["precio_adj"]],
                textposition="outside",
            )

        # Línea de tendencia oferta
        z = np.polyfit(range(len(anual)), anual["precio_oferta"], 1)
        tendencia = np.polyval(z, range(len(anual)))
        fig.add_scatter(
            x=anual["año"].astype(str),
            y=tendencia,
            mode="lines",
            name="Tendencia oferta",
            line=dict(color="#1e3a5f", width=2, dash="dash"),
        )

        fig.update_layout(
            title=f"Precio oferta vs adjudicado por año de vigencia ({ipp_label})",
            yaxis_title=f"$/kWh{sufijo_ind}",
            xaxis_title="Año de vigencia",
            barmode="group",
            height=420,
            plot_bgcolor="white",
            yaxis=dict(gridcolor="#f1f5f9"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_t:
        st.markdown(f"**Tabla anual** — {ipp_label}")
        df_tabla = anual.rename(columns={
            "año":            "Año",
            "precio_oferta":  f"Precio oferta ($/kWh{sufijo_ind})",
            "precio_adj":     f"Precio adj. ($/kWh{sufijo_ind})",
            "diferencia":     "Diferencia",
            "n_ofertas":      "N° ofertas",
        }).copy()

        def color_dif(val):
            if pd.isna(val): return ""
            return "color: #16a34a" if val < 0 else "color: #dc2626"

        st.dataframe(
            df_tabla.style
            .format({
                f"Precio oferta ($/kWh{sufijo_ind})": "${:,.2f}",
                f"Precio adj. ($/kWh{sufijo_ind})":   "${:,.2f}",
                "Diferencia": "{:+.2f}",
            })
            .map(color_dif, subset=["Diferencia"]),
            use_container_width=True,
            hide_index=True,
        )

# ══════════════════════════════════════════════════════════════
#  VISTA MENSUAL
# ══════════════════════════════════════════════════════════════
else:
    MES_MAP = {1:"Ene",2:"Feb",3:"Mar",4:"Abr",5:"May",6:"Jun",
               7:"Jul",8:"Ago",9:"Sep",10:"Oct",11:"Nov",12:"Dic"}

    mensual = (
        df_filt.groupby(["año", "mes_num"])
        .agg(
            precio_oferta = ("precio_oferta", "mean"),
            precio_adj    = ("precio_adj",    "mean"),
        )
        .round(2)
        .reset_index()
    )
    mensual["mes_label"] = mensual["mes_num"].map(MES_MAP)
    mensual["diferencia"] = (mensual["precio_adj"] - mensual["precio_oferta"]).round(2)

    # Filtro de año dentro de vista mensual
    años_mens = sorted(mensual["año"].unique().tolist())
    año_sel_mens = st.selectbox(
        "Año:",
        options=["Todos"] + [str(a) for a in años_mens],
        key="año_mensual_sel",
    )

    if mes_idx and ipp_valor:
        st.caption(f"Indexado a {mes_idx} · IPP {ipp_valor:.2f}")

    if año_sel_mens != "Todos":
        df_mens = mensual[mensual["año"] == int(año_sel_mens)].copy()
    else:
        df_mens = mensual.copy()

    # Tabla con subtotales por año (prom.)
    filas_tabla = []
    for año_v, grp in df_mens.groupby("año", sort=True):
        for _, r in grp.sort_values("mes_num").iterrows():
            filas_tabla.append({
                "Año":      int(año_v),
                "Mes":      r["mes_label"],
                f"Precio oferta ($/kWh{sufijo_ind})":  r["precio_oferta"],
                f"Precio adj. ($/kWh{sufijo_ind})":    r["precio_adj"],
                "Diferencia (adj - oferta)":           r["diferencia"],
            })
        # Fila de promedio anual
        filas_tabla.append({
            "Año":      f"Prom. {int(año_v)}",
            "Mes":      "",
            f"Precio oferta ($/kWh{sufijo_ind})":  grp["precio_oferta"].mean().round(2),
            f"Precio adj. ($/kWh{sufijo_ind})":    grp["precio_adj"].mean().round(2),
            "Diferencia (adj - oferta)":           grp["diferencia"].mean().round(2),
        })

    df_show = pd.DataFrame(filas_tabla)

    def estilo_fila(row):
        if str(row["Año"]).startswith("Prom."):
            return ["font-weight: bold; background-color: #f1f5f9"] * len(row)
        return [""] * len(row)

    def color_dif2(val):
        if pd.isna(val) or val == "": return ""
        try:
            return "color: #16a34a" if float(val) < 0 else "color: #dc2626"
        except:
            return ""

    st.dataframe(
        df_show.style
        .format({
            f"Precio oferta ($/kWh{sufijo_ind})": "${:,.2f}",
            f"Precio adj. ($/kWh{sufijo_ind})":   "${:,.2f}",
            "Diferencia (adj - oferta)": lambda v: f"{v:+.2f}" if pd.notna(v) else "",
        })
        .apply(estilo_fila, axis=1)
        .map(color_dif2, subset=["Diferencia (adj - oferta)"]),
        use_container_width=True,
        hide_index=True,
        height=600,
    )

st.markdown("---")

# ── Nota metodológica ────────────────────────────────────────
with st.expander("ℹ️ Metodología"):
    st.markdown(f"""
    - **Expansión mensual:** cada oferta se replica en todos los meses de su período de vigencia
      (`vigencia_inicio` → `vigencia_fin`), de modo que un contrato 2027–2032 aporta precio
      a cada uno de esos 72 meses.
    - **Precio adjudicado:** promedio de precios de las ofertas marcadas como `adjudicada = True`.
    - **Indexación:** {"activa con IPP " + str(mes_idx) + " (" + str(round(ipp_valor, 2)) + ")"
        if mes_idx and ipp_valor else "no disponible (archivo sin columna IPP)."}
    - **Diferencia:** `precio_adj − precio_oferta`. Negativo = el adjudicado fue más barato
      que el promedio de todo lo que se ofertó.
    """)

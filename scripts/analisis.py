# =============================================================
# analisis.py — Funciones analíticas core
# =============================================================

import pandas as pd
import numpy as np
from scipy import stats


# ─────────────────────────────────────────────────────────────
# 1. TIMING — ¿Cuándo abrir un proceso?
# ─────────────────────────────────────────────────────────────

def analisis_timing(master: pd.DataFrame, pb: pd.DataFrame) -> dict:
    """
    Responde: ¿en qué mes del año conviene más abrir un proceso de compra?

    Usa el spread histórico (precio_adj_prom - PB media 30d) como proxy de
    "qué tan buena fue la compra".
    Spread negativo = se contrató por DEBAJO de la PB → buen deal.
    """
    df = master[master["precio_adj_prom"].notna()].copy()

    # Por mes de audiencia
    por_mes = df.groupby("mes_audiencia").agg(
        n_procesos       = ("audiencia_id", "count"),
        spread_prom      = ("spread_vs_pb_30d", "mean"),
        spread_mediana   = ("spread_vs_pb_30d", "median"),
        precio_adj_prom  = ("precio_adj_prom", "mean"),
        pb_30d_prom      = ("pb_prom_30d", "mean"),
        pb_alta_pct      = ("pb_tendencia", lambda x: (x == "bajando").mean() * 100),
    ).round(2)

    meses_es = {1:"Ene",2:"Feb",3:"Mar",4:"Abr",5:"May",6:"Jun",
                7:"Jul",8:"Ago",9:"Sep",10:"Oct",11:"Nov",12:"Dic"}
    por_mes.index = [meses_es[m] for m in por_mes.index]
    por_mes = por_mes.sort_values("spread_prom")

    # Por año de vigencia requerido
    por_vigencia = {}
    if "año_vigencia" in df.columns:
        for yr in sorted(df["año_vigencia"].dropna().unique()):
        	sub = df[df["año_vigencia"] == yr]
        	if len(sub) >= 3:
        		por_vigencia[int(yr)] = sub.groupby("mes_audiencia").agg(
        		    n          = ("audiencia_id", "count"),
        		    spread_prom = ("spread_vs_pb_30d", "mean"),
        		    precio_adj  = ("precio_adj_prom", "mean"),
        		).round(2)

    # Estacionalidad PB pura (sin procesos)
    pb_estacional = pb.groupby("mes")["pb_prom_kwh"].agg(
        pb_prom = "mean", pb_p25 = lambda x: np.percentile(x.dropna(), 25),
        pb_p75  = lambda x: np.percentile(x.dropna(), 75),
    ).round(2)
    pb_estacional.index = [meses_es[m] for m in pb_estacional.index]

    return {
        "por_mes":       por_mes,
        "por_vigencia":  por_vigencia,
        "pb_estacional": pb_estacional,
    }


def mejor_mes_para_vigencia(master: pd.DataFrame, año_vigencia: int) -> pd.DataFrame:
    """Filtra procesos que sirven para `año_vigencia` y rankea por spread."""
    df = master[
        master["precio_adj_prom"].notna() &
        (master["año_vigencia"] == año_vigencia)
    ].copy()
    if len(df) == 0:
        return pd.DataFrame()

    meses_es = {1:"Ene",2:"Feb",3:"Mar",4:"Abr",5:"May",6:"Jun",
                7:"Jul",8:"Ago",9:"Sep",10:"Oct",11:"Nov",12:"Dic"}
    res = df.groupby("mes_audiencia").agg(
        n_procesos    = ("audiencia_id", "count"),
        spread_prom   = ("spread_vs_pb_30d", "mean"),
        precio_adj    = ("precio_adj_prom", "mean"),
        pb_30d_prom   = ("pb_prom_30d", "mean"),
    ).round(2).sort_values("spread_prom")
    res.index = [meses_es.get(m, m) for m in res.index]
    return res


# ─────────────────────────────────────────────────────────────
# 2. AGENTES — Perfil por generador
# ─────────────────────────────────────────────────────────────

def perfil_agentes(ofertas: pd.DataFrame,
                   pb: pd.DataFrame,
                   min_ofertas: int = 3) -> pd.DataFrame:
    """
    Construye tabla resumen por agente con:
    - n_ofertas, tasa_adjudicación, precio prom/min/max
    - horizonte promedio
    - meses de mayor actividad
    - spread sobre PB (a qué nivel de PB suelen ofertar)
    """
    # Cruzar con PB del día de audiencia
    pb_dia = pb[["fecha", "pb_prom_kwh"]].rename(
        columns={"fecha": "fecha_audiencia", "pb_prom_kwh": "pb_dia"}
    )
    df = ofertas.merge(pb_dia, on="fecha_audiencia", how="left")
    df["spread_vs_pb"] = df["precio_oferta"] - df["pb_dia"]

    perfil = df.groupby("agente_nombre").agg(
        n_ofertas           = ("audiencia_id", "count"),
        n_procesos          = ("audiencia_id", "nunique"),
        tasa_adjudicacion   = ("adjudicada", "mean"),
        precio_prom         = ("precio_oferta", "mean"),
        precio_min          = ("precio_oferta", "min"),
        precio_max          = ("precio_oferta", "max"),
        precio_mediana      = ("precio_oferta", "median"),
        horizonte_dias_prom = ("horizonte_dias", "mean"),
        horizonte_dias_med  = ("horizonte_dias", "median"),
        vigencia_años_prom  = ("vigencia_años", "mean"),
        spread_vs_pb_prom   = ("spread_vs_pb", "mean"),
        pb_cuando_oferta    = ("pb_dia", "mean"),
        primera_oferta      = ("fecha_audiencia", "min"),
        ultima_oferta       = ("fecha_audiencia", "max"),
    ).round(2)

    perfil["tasa_adj_pct"] = (perfil["tasa_adjudicacion"] * 100).round(1)
    perfil = perfil[perfil["n_ofertas"] >= min_ofertas].copy()
    perfil = perfil.sort_values("n_ofertas", ascending=False)
    return perfil


def estacionalidad_agente(ofertas: pd.DataFrame, agente: str) -> pd.Series:
    """Distribución de ofertas por mes para un agente específico."""
    sub = ofertas[ofertas["agente_nombre"] == agente]
    conteo = sub.groupby("mes_audiencia")["audiencia_id"].count()
    meses_es = {1:"Ene",2:"Feb",3:"Mar",4:"Abr",5:"May",6:"Jun",
                7:"Jul",8:"Ago",9:"Sep",10:"Oct",11:"Nov",12:"Dic"}
    conteo.index = [meses_es.get(m, m) for m in conteo.index]
    return conteo


def historial_agente(ofertas: pd.DataFrame, agente: str) -> pd.DataFrame:
    """Devuelve todas las ofertas de un agente con contexto."""
    cols = ["audiencia_id", "fecha_audiencia", "vigencia_inicio", "vigencia_fin",
            "precio_oferta", "cantidad_ofertada", "horizonte_dias", "adjudicada",
            "pct_adjudicado", "tipo_curva"]
    cols_exist = [c for c in cols if c in ofertas.columns]
    return (
        ofertas[ofertas["agente_nombre"] == agente][cols_exist]
        .sort_values("fecha_audiencia", ascending=False)
        .reset_index(drop=True)
    )


# ─────────────────────────────────────────────────────────────
# 3. ALERTAS — ¿Es buen momento para comprar ahora?
# ─────────────────────────────────────────────────────────────

def calcular_percentil_pb(pb: pd.DataFrame,
                          fecha_ref: pd.Timestamp = None,
                          ventana_hist_dias: int = 365 * 4) -> dict:
    """
    Calcula en qué percentil histórico está la PB actual.
    Percentil bajo → PB barata → cuidado (contratos pueden salir caros).
    Percentil alto  → PB cara  → buen momento para contratar largo plazo.
    """
    if fecha_ref is None:
        fecha_ref = pb["fecha"].max()

    hist = pb[pb["fecha"] <= fecha_ref].tail(ventana_hist_dias)
    pb_actual = float(hist["pb_prom_kwh"].iloc[-1])
    pb_30d    = float(hist.tail(30)["pb_prom_kwh"].mean())
    pb_90d    = float(hist.tail(90)["pb_prom_kwh"].mean())
    percentil = float(stats.percentileofscore(hist["pb_prom_kwh"].dropna(), pb_actual))

    tendencia_30d = float(hist.tail(30)["pb_prom_kwh"].diff().mean())

    señal = (
        "🟢 FUERTE — PB alta, contratos a buen precio relativo"
        if percentil >= 70 else
        "🟡 MODERADA — PB en rango medio"
        if percentil >= 40 else
        "🔴 ESPERAR — PB baja, el mercado probablemente no ofrezca buenos precios"
    )

    return {
        "fecha_ref":    fecha_ref.date(),
        "pb_actual":    round(pb_actual, 2),
        "pb_30d":       round(pb_30d, 2),
        "pb_90d":       round(pb_90d, 2),
        "percentil":    round(percentil, 1),
        "tendencia_30d": round(tendencia_30d, 2),
        "direccion":    "↑ subiendo" if tendencia_30d > 2 else ("↓ bajando" if tendencia_30d < -2 else "→ estable"),
        "señal":        señal,
    }


def alertas_vendedores_libres(ofertas: pd.DataFrame,
                               master: pd.DataFrame,
                               dias_ventana: int = 60) -> pd.DataFrame:
    """
    Identifica agentes con energía disponible en procesos recientes:
      1. No adjudicados al 0% (ofertaron y no ganaron nada)
      2. Adjudicados PARCIALMENTE (< 100%) → tienen remanente disponible

    Lógica:
    - Toma procesos de los últimos `dias_ventana` días (desde el último dato)
    - Incluye agentes con pct_adjudicado < 100
    - Agrega precio, horizonte y años de vigencia ofertados
    """
    # Usar el último dato de OFERTAS como referencia (no del master)
    # para evitar que la ventana caiga en un período sin datos de ofertas
    fecha_ref = ofertas["fecha_audiencia"].max()
    fecha_desde = fecha_ref - pd.Timedelta(days=dias_ventana)

    procesos_rec = master[master["fecha_audiencia"] >= fecha_desde]["audiencia_id"].tolist()

    # Incluir no adjudicados Y parcialmente adjudicados
    of_ventana = ofertas[ofertas["audiencia_id"].isin(procesos_rec)].copy()

    pct_col = "pct_adjudicado"
    if pct_col in of_ventana.columns:
        of_ventana[pct_col] = pd.to_numeric(of_ventana[pct_col], errors="coerce").fillna(0)
        # Disponible = no adj (0%) + parcial (0% < x < 100%)
        disponibles = of_ventana[of_ventana[pct_col] < 100].copy()
        disponibles["tipo_disponibilidad"] = disponibles[pct_col].apply(
            lambda x: "Sin adjudicar" if x == 0 else f"Parcial ({x:.0f}% adj.)"
        )
    else:
        disponibles = of_ventana[of_ventana["adjudicada"] == False].copy()
        disponibles["tipo_disponibilidad"] = "Sin adjudicar"

    if len(disponibles) == 0:
        return pd.DataFrame()

    # Años de vigencia ofertados
    def rango_vigencia(group):
        vi = pd.to_datetime(group["vigencia_inicio"], errors="coerce").dt.year.dropna()
        vf = pd.to_datetime(group["vigencia_fin"],   errors="coerce").dt.year.dropna()
        if len(vi) == 0:
            return "N/D"
        min_a, max_a = int(vi.min()), int(vf.max()) if len(vf) > 0 else int(vi.max())
        return str(min_a) if min_a == max_a else f"{min_a}–{max_a}"

    resumen = disponibles.groupby("agente_nombre").apply(
        lambda g: pd.Series({
            "veces_no_adj":      len(g),
            "procesos":          ", ".join(sorted(g["audiencia_id"].unique())[:3]),
            "precio_prom":       round(g["precio_oferta"].mean(), 2),
            "precio_min":        round(g["precio_oferta"].min(), 2),
            "ultima_audiencia":  g["fecha_audiencia"].max(),
            "horizonte_dias":    round(g["horizonte_dias"].mean(), 0) if "horizonte_dias" in g else None,
            "años_vigencia":     rango_vigencia(g),
            "tipo":              g["tipo_disponibilidad"].mode()[0] if len(g) > 0 else "",
        })
    ).reset_index().set_index("agente_nombre")

    return resumen.sort_values("ultima_audiencia", ascending=False)


def proyectar_mejor_momento(master: pd.DataFrame,
                             pb: pd.DataFrame,
                             año_vigencia_objetivo: int) -> dict:
    """
    Dado un año de vigencia requerido, proyecta el mejor momento para abrir.
    Combina:
    1. Patrón histórico de spread por mes
    2. Nivel actual de PB vs histórico
    3. Cuántos meses de anticipación suelen usarse
    """
    hist = mejor_mes_para_vigencia(master, año_vigencia_objetivo)
    estado_pb = calcular_percentil_pb(pb)

    if len(hist) == 0:
        recomendacion = "Sin datos históricos suficientes para este año de vigencia."
    else:
        mejor_mes  = hist.index[0]
        mejor_spread = hist["spread_prom"].iloc[0]
        horizonte_prom = master[
            (master["año_vigencia"] == año_vigencia_objetivo) &
            master["horizonte_meses"].notna()
        ]["horizonte_meses"].mean()

        recomendacion = (
            f"Históricamente, **{mejor_mes}** es el mejor mes para abrir un proceso "
            f"con vigencia en {año_vigencia_objetivo} (spread promedio: {mejor_spread:.0f} $/kWh). "
            f"El horizonte promedio de anticipación es {horizonte_prom:.0f} meses."
        )

    return {
        "ranking_meses":   hist,
        "estado_pb":       estado_pb,
        "recomendacion":   recomendacion,
    }

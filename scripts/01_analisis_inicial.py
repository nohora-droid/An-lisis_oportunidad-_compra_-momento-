# =============================================================================
# HERRAMIENTA DE ANÁLISIS DE COMPRA DE ENERGÍA - BIA ENERGY
# Script 01: Carga, limpieza y análisis exploratorio
# =============================================================================

import sys
import os
import warnings
warnings.filterwarnings("ignore")

# Forzar salida UTF-8 en Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

import pandas as pd
import numpy as np
from pathlib import Path

# ---------------------------------------------------------------------------
# RUTAS
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
RAW  = ROOT / "data" / "raw"
OUT  = ROOT / "data" / "outputs"
OUT.mkdir(parents=True, exist_ok=True)

SEP = "=" * 70

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------
def titulo(texto):
    print(f"\n{SEP}")
    print(f"  {texto}")
    print(SEP)

def subtitulo(texto):
    print(f"\n--- {texto} ---")

def leer_csv(nombre):
    """Lee con detección automática de encoding y separador."""
    path = RAW / nombre
    for enc in ["utf-8-sig", "utf-8", "latin-1"]:
        try:
            df = pd.read_csv(path, encoding=enc, sep=None, engine="python")
            # Limpiar BOM en nombres de columna
            df.columns = [c.lstrip("﻿").strip() for c in df.columns]
            print(f"  ✓ {nombre}: {len(df):,} filas × {len(df.columns)} columnas")
            return df
        except UnicodeDecodeError:
            continue
    raise ValueError(f"No se pudo leer {nombre}")


# ===========================================================================
# 1. CARGA
# ===========================================================================
titulo("1. CARGA DE DATOS")

pb      = leer_csv("pb_historica_diaria.csv")
ofertas = leer_csv("ofertas_por_agente_detalle.csv")
master  = leer_csv("master_con_pb.csv")


# ===========================================================================
# 2. LIMPIEZA
# ===========================================================================
titulo("2. LIMPIEZA")

# --- Precio de bolsa ---
pb["fecha"] = pd.to_datetime(pb["fecha"])
pb = pb.sort_values("fecha").reset_index(drop=True)
pb["año"]   = pb["fecha"].dt.year
pb["mes"]   = pb["fecha"].dt.month
pb["mes_nombre"] = pb["fecha"].dt.strftime("%b")
print(f"  PB: {pb['fecha'].min().date()} → {pb['fecha'].max().date()}")

# --- Ofertas por agente ---
for col in ["fecha_audiencia", "vigencia_inicio", "vigencia_fin", "fecha_limite_oferta"]:
    ofertas[col] = pd.to_datetime(ofertas[col], errors="coerce")

ofertas["año_audiencia"]   = ofertas["fecha_audiencia"].dt.year
ofertas["mes_audiencia"]   = ofertas["fecha_audiencia"].dt.month
ofertas["vigencia_años"]   = (
    (ofertas["vigencia_fin"] - ofertas["vigencia_inicio"]).dt.days / 365.25
).round(1)
ofertas["horizonte_dias"]  = (
    ofertas["vigencia_inicio"] - ofertas["fecha_audiencia"]
).dt.days
ofertas["adjudicada"]      = ofertas["adjudicada"].astype(bool)
print(f"  Ofertas: {ofertas['fecha_audiencia'].min().date()} → {ofertas['fecha_audiencia'].max().date()}")
print(f"  Agentes únicos: {ofertas['agente_nombre'].nunique()}")

# --- Master procesos ---
for col in ["fecha_audiencia", "fecha_inicio", "fecha_fin"]:
    master[col] = pd.to_datetime(master[col], errors="coerce")

master["año_audiencia"] = master["fecha_audiencia"].dt.year
master["mes_audiencia"] = master["fecha_audiencia"].dt.month
master["año_vigencia"]  = master["fecha_inicio"].dt.year
master_adj = master[master["precio_adj_prom"].notna()].copy()
print(f"  Master: {len(master):,} procesos | {len(master_adj):,} con adjudicación")


# ===========================================================================
# 3. ANÁLISIS DEL PRECIO DE BOLSA
# ===========================================================================
titulo("3. PRECIO DE BOLSA HISTÓRICO ($/kWh)")

# Estadísticas anuales
pb_anual = pb.groupby("año")["pb_prom_kwh"].agg(
    promedio="mean", mínimo="min", máximo="max", std="std"
).round(2)
print(pb_anual.to_string())

# Promedio mensual histórico (estacionalidad)
subtitulo("Estacionalidad mensual (promedio histórico por mes)")
meses_order = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
pb_mensual = pb.groupby("mes")["pb_prom_kwh"].agg(
    promedio="mean", mínimo="min", máximo="max"
).round(2)
pb_mensual.index = [
    ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"][m-1]
    for m in pb_mensual.index
]
print(pb_mensual.to_string())

# Meses más baratos / más caros históricamente
subtitulo("Top 3 meses MÁS BARATOS históricamente")
print(pb_mensual["promedio"].nsmallest(3).to_string())

subtitulo("Top 3 meses MÁS CAROS históricamente")
print(pb_mensual["promedio"].nlargest(3).to_string())


# ===========================================================================
# 4. ¿CUÁNDO ABRIR UN PROCESO? — análisis por año de vigencia
# ===========================================================================
titulo("4. MEJOR MOMENTO PARA ABRIR PROCESO (por año de vigencia requerido)")

if "precio_adj_prom" in master_adj.columns and "pb_prom_30d" in master_adj.columns:

    subtitulo("Spread precio adjudicado vs PB (30d antes de audiencia)")
    spread_stats = master_adj.groupby("año_audiencia").agg(
        n_procesos=("audiencia_id", "count"),
        pb_30d_prom=("pb_prom_30d", "mean"),
        precio_adj_prom=("precio_adj_prom", "mean"),
        spread_prom=("spread_vs_pb_30d", "mean"),
        pb_tendencia_baja=("pb_tendencia", lambda x: (x=="bajando").sum()),
    ).round(2)
    print(spread_stats.to_string())

    subtitulo("Procesos con menor spread (mejores compras históricas — top 10)")
    top_compras = master_adj.nsmallest(10, "spread_vs_pb_30d")[
        ["audiencia_id", "fecha_audiencia", "comprador",
         "precio_adj_prom", "pb_prom_30d", "spread_vs_pb_30d",
         "pb_tendencia", "horizonte_meses"]
    ]
    print(top_compras.to_string(index=False))

    # Mejor mes del año para abrir proceso
    subtitulo("Mes promedio con menor spread (¿cuándo abrir?)")
    master_adj["mes_audiencia_nombre"] = master_adj["fecha_audiencia"].dt.strftime("%b")
    por_mes = master_adj.groupby("mes_audiencia").agg(
        n=("audiencia_id", "count"),
        spread_prom=("spread_vs_pb_30d", "mean"),
        precio_adj=("precio_adj_prom", "mean"),
    ).round(2).sort_values("spread_prom")
    por_mes.index = [
        ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"][int(m)-1]
        for m in por_mes.index
    ]
    print(por_mes.to_string())

else:
    subtitulo("Distribución de procesos por mes de audiencia")
    print(master_adj.groupby("mes_audiencia")["audiencia_id"].count().to_string())


# ===========================================================================
# 5. ANÁLISIS POR AGENTE
# ===========================================================================
titulo("5. ANÁLISIS POR AGENTE")

subtitulo("Resumen general por agente")
agente_res = ofertas.groupby("agente_nombre").agg(
    n_ofertas=("audiencia_id", "count"),
    tasa_adjudicacion=("adjudicada", "mean"),
    precio_prom=("precio_oferta", "mean"),
    precio_min=("precio_oferta", "min"),
    precio_max=("precio_oferta", "max"),
    horizonte_dias_prom=("horizonte_dias", "mean"),
).round(2).sort_values("n_ofertas", ascending=False)
agente_res["tasa_adjudicacion"] = (agente_res["tasa_adjudicacion"] * 100).round(1)
agente_res.rename(columns={"tasa_adjudicacion": "tasa_adj_%"}, inplace=True)
print(agente_res.to_string())

subtitulo("Agentes con mayor tasa de adjudicación (mín 5 ofertas)")
top_adj = agente_res[agente_res["n_ofertas"] >= 5].nlargest(10, "tasa_adj_%")
print(top_adj[["n_ofertas", "tasa_adj_%", "precio_prom", "horizonte_dias_prom"]].to_string())

subtitulo("Estacionalidad por agente (top 8 más activos)")
top_agentes = agente_res.nlargest(8, "n_ofertas").index.tolist()
est_agente = (
    ofertas[ofertas["agente_nombre"].isin(top_agentes)]
    .groupby(["agente_nombre", "mes_audiencia"])["audiencia_id"]
    .count()
    .unstack(fill_value=0)
)
est_agente.columns = [
    ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"][m-1]
    for m in est_agente.columns
]
print(est_agente.to_string())

subtitulo("Horizonte de anticipación por agente (días entre audiencia e inicio vigencia)")
horizonte = (
    ofertas[ofertas["agente_nombre"].isin(top_agentes)]
    .groupby("agente_nombre")["horizonte_dias"]
    .agg(prom="mean", mediana="median", min="min", max="max")
    .round(0)
    .astype(int)
)
print(horizonte.to_string())


# ===========================================================================
# 6. CRUCE AGENTE × PB — ¿ofertaron en momentos de PB alta o baja?
# ===========================================================================
titulo("6. ¿A QUÉ NIVEL DE PB OFERTA CADA AGENTE?")

ofertas_pb = ofertas.merge(
    pb[["fecha", "pb_prom_kwh"]].rename(columns={"fecha": "fecha_audiencia"}),
    on="fecha_audiencia", how="left"
)
ofertas_pb["spread_vs_pb"] = ofertas_pb["precio_oferta"] - ofertas_pb["pb_prom_kwh"]

spread_agente = (
    ofertas_pb[ofertas_pb["agente_nombre"].isin(top_agentes)]
    .groupby("agente_nombre")
    .agg(
        pb_prom_cuando_oferta=("pb_prom_kwh", "mean"),
        precio_oferta_prom=("precio_oferta", "mean"),
        spread_sobre_pb=("spread_vs_pb", "mean"),
    )
    .round(2)
    .sort_values("spread_sobre_pb")
)
print(spread_agente.to_string())


# ===========================================================================
# 7. EXPORTAR RESÚMENES
# ===========================================================================
titulo("7. EXPORTANDO RESÚMENES A data/outputs/")

pb_mensual.to_csv(OUT / "pb_estacionalidad_mensual.csv")
agente_res.to_csv(OUT / "resumen_por_agente.csv")
por_mes.to_csv(OUT / "mejor_mes_apertura_proceso.csv")
spread_agente.to_csv(OUT / "spread_agente_vs_pb.csv")

print("  ✓ pb_estacionalidad_mensual.csv")
print("  ✓ resumen_por_agente.csv")
print("  ✓ mejor_mes_apertura_proceso.csv")
print("  ✓ spread_agente_vs_pb.csv")

titulo("ANÁLISIS COMPLETADO ✓")
print(f"  Archivos de salida en: {OUT}\n")

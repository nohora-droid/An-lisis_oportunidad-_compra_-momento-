# =============================================================
# pipeline_actualizar.py
# Regenera ofertas_por_agente_detalle.csv y master_con_pb.csv
#
# Fuente de ofertas (en orden de prioridad):
#   1. API interna BIA  GET /v1/convocatorias  (si hay red BIA/VPN + API key)
#   2. audiencias_master.xlsx  (descargado de Drive)
#
# Uso: python scripts/pipeline_actualizar.py
#      python scripts/pipeline_actualizar.py --forzar-xlsx   (omite API)
# =============================================================

import sys
import re
import warnings
import pandas as pd
import numpy as np
from pathlib import Path

warnings.filterwarnings("ignore")

FORZAR_XLSX = "--forzar-xlsx" in sys.argv

ROOT = Path(__file__).resolve().parent.parent
RAW  = ROOT / "data" / "raw"


# -------------------------------------------------------------
# Helpers
# -------------------------------------------------------------

def limpiar_id(s):
    return re.sub(r"[^A-Z0-9\-]", "", str(s).strip().upper())


def es_adjudicada(val):
    return str(val).strip() in ["Sí", "SI", "si", "sí", "S", "Yes", "YES",
                                 "True", "TRUE", "S\xed", "Sí",
                                 "S?", "S†"]   # maneja encoding issues


def normalizar_fecha(col, dayfirst=True):
    return pd.to_datetime(col, dayfirst=dayfirst, errors="coerce")


# -------------------------------------------------------------
# 1. Cargar archivos fuente
# -------------------------------------------------------------

print("=" * 60)
print("Paso 1: Cargando archivos fuente...")

# -- Intentar API primero, sino usar xlsx local ---
USAR_API = False
if not FORZAR_XLSX:
    try:
        from scripts.api_client import api_disponible, descargar_convocatorias, normalizar_respuesta
        if api_disponible():
            USAR_API = True
            print("  [API] Red BIA detectada -> usando /v1/convocatorias")
        else:
            print("  [INFO] API no alcanzable (sin VPN/red BIA) -> usando xlsx local")
    except Exception as e:
        print(f"  [INFO] api_client no disponible ({e}) -> usando xlsx local")
else:
    print("  [INFO] Modo --forzar-xlsx activo")

if USAR_API:
    print("  Descargando convocatorias desde API...")
    df_api = descargar_convocatorias(verbose=True)
    df_api_norm = normalizar_respuesta(df_api)
    # Guardar como xlsx para respaldo local
    df_api.to_excel(RAW / "audiencias_master.xlsx", index=False, engine="openpyxl")
    print(f"  Respaldo guardado en audiencias_master.xlsx")
    aud_raw = df_api   # se usará en pasos siguientes
else:
    aud_raw = pd.read_excel(RAW / "audiencias_master.xlsx", sheet_name=0, engine="openpyxl")

sol_raw = pd.read_excel(RAW / "solicitado_master.xlsx", sheet_name=0, engine="openpyxl")
pb_raw  = pd.read_csv(RAW / "pb_historica_diaria.csv", encoding="utf-8-sig")

print(f"  audiencias_master : {len(aud_raw):,} filas  x {len(aud_raw.columns)} cols")
print(f"  solicitado_master : {len(sol_raw):,} filas  x {len(sol_raw.columns)} cols")
print(f"  pb_historica      : {len(pb_raw):,} filas")


# -------------------------------------------------------------
# 2. Limpiar audiencias_master
# -------------------------------------------------------------

print("\nPaso 2: Limpiando audiencias_master...")

df_aud = aud_raw.copy()

# Eliminar columnas unnamed
df_aud = df_aud[[c for c in df_aud.columns if not str(c).lower().startswith("unnamed")]]

# Limpiar IDs
df_aud["audiencia_id"] = df_aud["audiencia_id"].apply(limpiar_id)
df_aud = df_aud[df_aud["audiencia_id"].notna() & (df_aud["audiencia_id"] != "")]

# Fechas
df_aud["AudienciaPublica"]            = normalizar_fecha(df_aud["AudienciaPublica"])
df_aud["FechaLimiteRecepcionOfertas"] = normalizar_fecha(df_aud["FechaLimiteRecepcionOfertas"])
df_aud["fecha inicio producto"]       = normalizar_fecha(df_aud["fecha inicio producto"])
df_aud["fecha fin producto"]          = normalizar_fecha(df_aud["fecha fin producto"])

# IPP reference date -> keep as date (YYYY-MM-01)
if "ipp" in df_aud.columns:
    df_aud["ipp_fecha"] = pd.to_datetime(df_aud["ipp"], errors="coerce")

# Numerics
df_aud["precio_oferta"]  = pd.to_numeric(df_aud["precio_oferta"],  errors="coerce")
df_aud["cantidad_oferta"] = pd.to_numeric(df_aud["cantidad_oferta"], errors="coerce")
df_aud["porcentaje_adj"] = pd.to_numeric(df_aud["porcentaje_adj"], errors="coerce").fillna(0)

# Oferta number
if "oferta" not in df_aud.columns:
    df_aud["oferta"] = 1
else:
    df_aud["oferta"] = pd.to_numeric(df_aud["oferta"], errors="coerce").fillna(1)

# Adjudicada bool
df_aud["adjudicada_bool"] = df_aud["adjudicada"].apply(es_adjudicada)
adj_n   = df_aud["adjudicada_bool"].sum()
no_adj_n = (~df_aud["adjudicada_bool"]).sum()
print(f"  Adjudicadas: {adj_n:,}  |  No adjudicadas: {no_adj_n:,}")

# Nombre de agente legible
if "agente_corto" in df_aud.columns:
    df_aud["agente_nombre"] = (
        df_aud["agente_corto"].astype(str).str.strip().str.title()
    )
else:
    df_aud["agente_nombre"] = df_aud["agente"].astype(str).str.strip().str.upper()

print(f"  Audiencias únicas : {df_aud['audiencia_id'].nunique()}")
print(f"  Agentes únicos    : {df_aud['agente'].nunique()}")
print(f"  Rango de fechas   : {df_aud['AudienciaPublica'].min().date()} -> {df_aud['AudienciaPublica'].max().date()}")


# -------------------------------------------------------------
# 3. Construir ofertas_por_agente_detalle.csv
# -------------------------------------------------------------

print("\nPaso 3: Construyendo ofertas_por_agente_detalle...")

grp = ["audiencia_id", "agente", "producto", "oferta"]

ofertas = (
    df_aud.groupby(grp, dropna=False)
    .agg(
        fecha_audiencia        = ("AudienciaPublica",            "first"),
        fecha_limite_oferta    = ("FechaLimiteRecepcionOfertas", "first"),
        vigencia_inicio        = ("fecha inicio producto",       "min"),
        vigencia_fin           = ("fecha fin producto",          "max"),
        tipo_mercado           = ("TipoMercado",                 "first"),
        agente_nombre          = ("agente_nombre",               "first"),
        cantidad_ofertada      = ("cantidad_oferta",             "sum"),
        precio_oferta          = ("precio_oferta",               "mean"),
        pct_adjudicado         = ("porcentaje_adj",              "mean"),
        adjudicada             = ("adjudicada_bool",             "any"),
        tipo_curva             = ("curva - plano",               "first"),
        ipp_fecha              = ("ipp_fecha",                   "first"),
    )
    .reset_index()
)

ofertas = ofertas.rename(columns={
    "agente":   "agente_codigo",
    "producto": "producto_id",
    "oferta":   "oferta_num",
})

# Agente iniciales (primeras 3 letras del código)
ofertas["agente_iniciales"] = (
    ofertas["agente_codigo"].astype(str).str[:3].str.upper()
)

# Tipo curva limpio
ofertas["tipo_curva"] = (
    ofertas["tipo_curva"].astype(str).str.strip().str.upper()
    .replace("NAN", "PLANO")
)

# Reordenar columnas para que quede igual al CSV original
cols_orden = [
    "audiencia_id", "fecha_audiencia", "fecha_limite_oferta",
    "vigencia_inicio", "vigencia_fin", "tipo_mercado",
    "agente_codigo", "agente_iniciales", "agente_nombre",
    "cantidad_ofertada", "precio_oferta", "pct_adjudicado",
    "adjudicada", "tipo_curva", "ipp_fecha",
    "producto_id", "oferta_num",
]
cols_exist = [c for c in cols_orden if c in ofertas.columns]
ofertas = ofertas[cols_exist]

out_ofertas = RAW / "ofertas_por_agente_detalle.csv"
ofertas.to_csv(out_ofertas, index=False, encoding="utf-8-sig")
print(f"  [OK] {len(ofertas):,} filas -> {out_ofertas.name}")


# -------------------------------------------------------------
# 4. Limpiar solicitado_master
# -------------------------------------------------------------

print("\nPaso 4: Limpiando solicitado_master...")

df_sol = sol_raw.copy()
df_sol = df_sol[[c for c in df_sol.columns if not str(c).lower().startswith("unnamed")]]

df_sol["audiencia_id"] = df_sol["audiencia_id"].apply(limpiar_id)
df_sol = df_sol[df_sol["audiencia_id"].notna() & (df_sol["audiencia_id"] != "")]

df_sol["AudienciaPublica"]     = normalizar_fecha(df_sol["AudienciaPublica"])
df_sol["fecha inicio producto"] = normalizar_fecha(df_sol["fecha inicio producto"])
df_sol["fecha fin producto"]   = normalizar_fecha(df_sol["fecha fin producto"])
df_sol["cantidad_solicitada"]  = pd.to_numeric(df_sol["cantidad_solicitada"], errors="coerce")

print(f"  Audiencias únicas : {df_sol['audiencia_id'].nunique()}")


# -------------------------------------------------------------
# 5. Master procesos — 1 fila por audiencia
# -------------------------------------------------------------

print("\nPaso 5: Construyendo master_procesos...")

# -- 5a. Resumen de lo solicitado ----------------------------
resumen_sol = (
    df_sol.groupby("audiencia_id")
    .agg(
        fecha_audiencia    = ("AudienciaPublica",      "first"),
        comprador          = ("agente_comprador",      "first"),
        mercado            = ("TipoMercado",           "first"),
        n_productos        = ("producto",              "nunique"),
        fecha_inicio       = ("fecha inicio producto", "min"),
        fecha_fin          = ("fecha fin producto",    "max"),
        cantidad_total_kwh = ("cantidad_solicitada",   "sum"),
    )
    .reset_index()
)

resumen_sol["cantidad_total_gwh"] = (resumen_sol["cantidad_total_kwh"] / 1_000_000).round(6)
resumen_sol["horizonte_meses"]   = (
    (resumen_sol["fecha_fin"] - resumen_sol["fecha_inicio"]).dt.days / 30
).round(0).astype("Int64")

# -- 5b. Resumen de adjudicaciones ---------------------------
adj = df_aud[df_aud["adjudicada_bool"]].copy()

if len(adj) > 0:
    resumen_adj = (
        adj.groupby("audiencia_id")
        .agg(
            fecha_audiencia_res = ("AudienciaPublica",            "first"),
            fecha_limite_oferta = ("FechaLimiteRecepcionOfertas", "first"),
            adjudicatario       = ("agente_nombre", lambda x: x.mode().iloc[0] if len(x) > 0 else None),
            precio_adj_prom     = ("precio_oferta",  "mean"),
            precio_adj_min      = ("precio_oferta",  "min"),
            precio_adj_max      = ("precio_oferta",  "max"),
            cantidad_adj_gwh    = ("cantidad_oferta", "sum"),
        )
        .reset_index()
    )
    # n_oferentes: todos los agentes que ofertaron (adj + no adj)
    n_of = (
        df_aud.groupby("audiencia_id")["agente"]
        .nunique()
        .reset_index()
        .rename(columns={"agente": "n_oferentes"})
    )
    resumen_adj = resumen_adj.merge(n_of, on="audiencia_id", how="left")
    # Oferentes lista
    oferentes_lista = (
        df_aud.groupby("audiencia_id")["agente_nombre"]
        .apply(lambda x: ", ".join(sorted(x.dropna().unique())))
        .reset_index()
        .rename(columns={"agente_nombre": "oferentes_lista"})
    )
    resumen_adj = resumen_adj.merge(oferentes_lista, on="audiencia_id", how="left")
else:
    resumen_adj = pd.DataFrame(columns=[
        "audiencia_id", "fecha_audiencia_res", "fecha_limite_oferta",
        "adjudicatario", "precio_adj_prom", "precio_adj_min", "precio_adj_max",
        "cantidad_adj_gwh", "n_oferentes", "oferentes_lista",
    ])

# -- 5c. Join ------------------------------------------------
df_master = resumen_sol.merge(resumen_adj, on="audiencia_id", how="left")

df_master["cobertura_pct"] = (
    df_master["cantidad_adj_gwh"] / df_master["cantidad_total_gwh"] * 100
).round(1)
df_master["dias_proceso"] = (
    df_master["fecha_audiencia_res"] - df_master["fecha_audiencia"]
).dt.days

print(f"  Procesos totales    : {len(df_master)}")
print(f"  Con precio adj      : {df_master['precio_adj_prom'].notna().sum()}")
print(f"  Sin resultado aún   : {df_master['precio_adj_prom'].isna().sum()}")


# -------------------------------------------------------------
# 6. Unir con PB histórica -> master_con_pb.csv
# -------------------------------------------------------------

print("\nPaso 6: Enriqueciendo con Precio de Bolsa...")

# Limpiar PB
pb_raw.columns = [c.lstrip("﻿").strip() for c in pb_raw.columns]
pb = pb_raw.copy()
pb["fecha"] = pd.to_datetime(pb["fecha"])
pb = pb.sort_values("fecha").reset_index(drop=True)
pb["pb_val"] = pd.to_numeric(pb["pb_prom_kwh"], errors="coerce")

pb_indexed = pb.set_index("fecha")["pb_val"]

print(f"  PB disponible: {pb['fecha'].min().date()} -> {pb['fecha'].max().date()}")


def pb_window(fecha_ref, dias, pb_series):
    """Estadísticas de PB en los `dias` días anteriores a fecha_ref."""
    if pd.isna(fecha_ref):
        return {k: np.nan for k in ["prom", "min", "max", "std", "trend"]}
    fecha_desde = fecha_ref - pd.Timedelta(days=dias)
    mask = (pb_series.index >= fecha_desde) & (pb_series.index <= fecha_ref)
    vals = pb_series[mask].dropna()
    if len(vals) < 5:
        return {k: np.nan for k in ["prom", "min", "max", "std", "trend"]}
    trend = float(np.polyfit(range(len(vals)), vals.values, 1)[0])
    return {
        "prom":  round(float(vals.mean()),  2),
        "min":   round(float(vals.min()),   2),
        "max":   round(float(vals.max()),   2),
        "std":   round(float(vals.std()),   2),
        "trend": round(trend,               4),
    }


rows_pb = []
for _, row in df_master.iterrows():
    fecha = row["fecha_audiencia"]
    pb_dia_val = pb_indexed.get(fecha, np.nan)
    if pd.isna(pb_dia_val):
        # Buscar fecha más cercana (±3 días)
        for d in range(1, 4):
            for delta in [d, -d]:
                alt = fecha + pd.Timedelta(days=delta)
                v   = pb_indexed.get(alt, np.nan)
                if not pd.isna(v):
                    pb_dia_val = v
                    break
            if not pd.isna(pb_dia_val):
                break

    w30 = pb_window(fecha, 30,  pb_indexed)
    w60 = pb_window(fecha, 60,  pb_indexed)
    w90 = pb_window(fecha, 90,  pb_indexed)

    # pb_relativa_90d: pb actual / pb_prom_90d
    pb_rel = round(pb_dia_val / w90["prom"], 4) if (w90["prom"] and not pd.isna(pb_dia_val)) else np.nan

    # Tendencia: subiendo/bajando/estable basado en trend 30d
    if not pd.isna(w30["trend"]):
        tendencia = "subiendo" if w30["trend"] > 1.5 else ("bajando" if w30["trend"] < -1.5 else "estable")
    else:
        tendencia = np.nan

    rows_pb.append({
        "pb_dia":         round(pb_dia_val, 4) if not pd.isna(pb_dia_val) else np.nan,
        "pb_prom_30d":    w30["prom"],
        "pb_min_30d":     w30["min"],
        "pb_max_30d":     w30["max"],
        "pb_std_30d":     w30["std"],
        "pb_trend_30d":   w30["trend"],
        "pb_prom_60d":    w60["prom"],
        "pb_min_60d":     w60["min"],
        "pb_max_60d":     w60["max"],
        "pb_std_60d":     w60["std"],
        "pb_trend_60d":   w60["trend"],
        "pb_prom_90d":    w90["prom"],
        "pb_min_90d":     w90["min"],
        "pb_max_90d":     w90["max"],
        "pb_std_90d":     w90["std"],
        "pb_trend_90d":   w90["trend"],
        "pb_relativa_90d": pb_rel,
        "pb_tendencia":    tendencia,
    })

df_pb = pd.DataFrame(rows_pb)
df_master_pb = pd.concat([df_master.reset_index(drop=True), df_pb], axis=1)

# Calcular spreads
df_master_pb["spread_vs_pb_dia"]  = (df_master_pb["precio_adj_prom"] - df_master_pb["pb_dia"]).round(4)
df_master_pb["spread_vs_pb_30d"]  = (df_master_pb["precio_adj_prom"] - df_master_pb["pb_prom_30d"]).round(4)
df_master_pb["spread_vs_pb_90d"]  = (df_master_pb["precio_adj_prom"] - df_master_pb["pb_prom_90d"]).round(4)

# También: mes_audiencia para el análisis de timing
df_master_pb["mes_audiencia"] = pd.to_datetime(df_master_pb["fecha_audiencia"]).dt.month
df_master_pb["año_audiencia"] = pd.to_datetime(df_master_pb["fecha_audiencia"]).dt.year

# Guardar
out_master = RAW / "master_con_pb.csv"
df_master_pb.to_csv(out_master, index=False, encoding="utf-8-sig")
print(f"  [OK] {len(df_master_pb)} procesos -> {out_master.name}")
print(f"  Rango fechas: {df_master_pb['fecha_audiencia'].min()} -> {df_master_pb['fecha_audiencia'].max()}")


# -------------------------------------------------------------
# 7. Resumen final
# -------------------------------------------------------------

print("\n" + "=" * 60)
print("[OK] Pipeline completado.")
print(f"   ofertas_por_agente_detalle.csv : {len(ofertas):,} filas")
print(f"   master_con_pb.csv             : {len(df_master_pb)} procesos")
print(f"   Audiencias más recientes      :")
top5 = (
    df_master_pb[["audiencia_id", "fecha_audiencia", "comprador", "precio_adj_prom"]]
    .sort_values("fecha_audiencia", ascending=False)
    .head(5)
)
for _, r in top5.iterrows():
    adj_str = f"${r['precio_adj_prom']:,.0f}/kWh" if pd.notna(r['precio_adj_prom']) else "pendiente"
    print(f"   {r['audiencia_id']}  {r['fecha_audiencia'].strftime('%d/%m/%Y') if pd.notna(r['fecha_audiencia']) else 'N/D'}  {r['comprador']}  {adj_str}")
print("=" * 60)

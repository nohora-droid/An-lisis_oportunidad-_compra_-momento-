# =============================================================
# data_loader.py — Carga y caché de datos
# =============================================================
"""
Carga los archivos de datos desde local (data/raw/) con caché en memoria.
Si se quiere sincronizar desde Drive, usar sync_from_drive().
"""

import sys
import pandas as pd
import numpy as np
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent
RAW  = ROOT / "data" / "raw"
PROC = ROOT / "data" / "processed"
PROC.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Utilidades de lectura
# ---------------------------------------------------------------------------
def _leer_csv(nombre: str) -> pd.DataFrame:
    path = RAW / nombre
    for enc in ["utf-8-sig", "utf-8", "latin-1"]:
        try:
            df = pd.read_csv(path, encoding=enc, sep=None, engine="python")
            df.columns = [c.lstrip("﻿").strip() for c in df.columns]
            return df
        except (UnicodeDecodeError, pd.errors.ParserError):
            continue
    raise FileNotFoundError(f"No se pudo leer {path}")


def _leer_excel(nombre: str, sheet: int = 0) -> pd.DataFrame:
    path = RAW / nombre
    return pd.read_excel(path, sheet_name=sheet, engine="openpyxl")


# ---------------------------------------------------------------------------
# Carga de datos individuales
# ---------------------------------------------------------------------------
def cargar_pb() -> pd.DataFrame:
    """Precio de bolsa diario TxF (2022–presente)."""
    df = _leer_csv("pb_historica_diaria.csv")
    df["fecha"] = pd.to_datetime(df["fecha"])
    df = df.sort_values("fecha").reset_index(drop=True)
    df["año"]  = df["fecha"].dt.year
    df["mes"]  = df["fecha"].dt.month
    df["trim"] = df["fecha"].dt.quarter
    return df


def cargar_ofertas() -> pd.DataFrame:
    """1,627 ofertas históricas por agente (detalle)."""
    df = _leer_csv("ofertas_por_agente_detalle.csv")
    for col in ["fecha_audiencia", "vigencia_inicio", "vigencia_fin", "fecha_limite_oferta"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    df["adjudicada"]     = df["adjudicada"].astype(bool)
    df["horizonte_dias"] = (df["vigencia_inicio"] - df["fecha_audiencia"]).dt.days
    df["vigencia_años"]  = (
        (df["vigencia_fin"] - df["vigencia_inicio"]).dt.days / 365.25
    ).round(1)
    df["año_audiencia"] = df["fecha_audiencia"].dt.year
    df["mes_audiencia"] = df["fecha_audiencia"].dt.month
    return df


def cargar_master() -> pd.DataFrame:
    """Tabla maestra: 353 procesos + contexto de PB."""
    df = _leer_csv("master_con_pb.csv")
    for col in ["fecha_audiencia", "fecha_inicio", "fecha_fin",
                "fecha_limite_oferta", "fecha_audiencia_res"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    df["año_audiencia"] = df["fecha_audiencia"].dt.year
    df["mes_audiencia"] = df["fecha_audiencia"].dt.month
    df["año_vigencia"]  = df["fecha_inicio"].dt.year
    return df


def cargar_pronostico() -> pd.DataFrame:
    """
    Pronóstico de PB diario por escenario (base/húmedo/seco).

    Estructura de salida (una fila por fecha):
        fecha | base_p10 | base_p50 | base_p90
              | humedo_mean | seco_mean

    El CSV fuente tiene hasta 9 filas por fecha:
      - base  : p10 / p50 / p90 (percentile column)
      - humedo: 3 filas con percentile='mean' → se promedia
      - seco  : 3 filas con percentile='mean' → se promedia
    """
    path = RAW / "pronostico_pb_oficial.csv"
    if not path.exists():
        return pd.DataFrame()

    df = pd.read_csv(path)
    df["fecha"] = pd.to_datetime(df["fecha"])
    df.columns = [c.strip().lower() for c in df.columns]

    # ── Base: pivot p10 / p50 / p90 ─────────────────────────
    base = (
        df[df["scenario"] == "base"]
        .pivot_table(index="fecha", columns="percentile", values="pb_prom_kwh", aggfunc="mean")
        .rename(columns={"p10": "base_p10", "p50": "base_p50", "p90": "base_p90"})
    )

    # ── Húmedo y seco: media de sus 3 filas por fecha ────────
    for scen in ["humedo", "seco"]:
        col = f"{scen}_mean"
        agg = (
            df[df["scenario"] == scen]
            .groupby("fecha")["pb_prom_kwh"]
            .mean()
            .rename(col)
        )
        base = base.join(agg, how="left")

    base = base.reset_index().sort_values("fecha")
    return base


def cargar_ipp() -> pd.DataFrame:
    """Serie IPP mensual para indexación de precios."""
    # Primero CSV, luego Excel
    for nombre in ["ipp_serie.csv", "ipp_serie.xlsx", "Serie Ipp oferta interna.xlsx"]:
        path = RAW / nombre
        if not path.exists():
            continue
        if nombre.endswith(".csv"):
            df = pd.read_csv(path)
        else:
            df = pd.read_excel(path, engine="openpyxl")
        df.columns = [c.strip().lower() for c in df.columns]
        fecha_col = next((c for c in df.columns if "fecha" in c or "date" in c), df.columns[0])
        ipp_col   = next((c for c in df.columns if "ipp" in c), df.columns[1])
        df = df.rename(columns={fecha_col: "fecha", ipp_col: "ipp"})
        df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
        df = df.dropna(subset=["fecha", "ipp"]).sort_values("fecha").reset_index(drop=True)
        return df[["fecha", "ipp"]]
    # Fallback sintético
    return pd.DataFrame({"fecha": pd.date_range("2022-07-01", periods=24, freq="MS"),
                         "ipp": [171.4] * 24})


# ---------------------------------------------------------------------------
# Carga conjunta (para uso en Streamlit con @st.cache_data)
# ---------------------------------------------------------------------------
def cargar_todo() -> dict:
    """Retorna todos los DataFrames listos para análisis."""
    return {
        "pb":          cargar_pb(),
        "ofertas":     cargar_ofertas(),
        "master":      cargar_master(),
        "ipp":         cargar_ipp(),
        "pronostico":  cargar_pronostico(),
    }

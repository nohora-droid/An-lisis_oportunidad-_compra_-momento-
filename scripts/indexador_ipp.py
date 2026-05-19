# =============================================================
# indexador_ipp.py — Indexación de precios con IPP
# Lógica tomada de: Sicep insight/Definitivos/indexar_precios.py
# =============================================================
"""
Cada oferta en audiencias_master tiene una columna 'IPP' que indica
el mes de referencia al que pertenece su precio_oferta.

La indexación lleva todos los precios a un mes_objetivo común:
    precio_indexado = precio_oferta × (IPP_objetivo / IPP_base)

Columnas esperadas:
  - df_consolidado : 'precio_oferta'  (float)  y  'IPP' (fecha, cualquier formato)
  - df_ipp         : 'Fecha'          (datetime) y  'IPP' (float — valor del índice)
"""

import pandas as pd
import numpy as np


def indexar_precios_por_mes(df_consolidado: pd.DataFrame,
                             df_ipp: pd.DataFrame,
                             mes_objetivo: str) -> pd.DataFrame:
    """
    Aplica indexación de precios a un DataFrame de audiencias según IPP.

    Parámetros:
        df_consolidado : DataFrame con columnas 'precio_oferta' e 'IPP' (fecha de referencia)
        df_ipp         : DataFrame con columnas 'Fecha' (datetime) e 'IPP' (float)
        mes_objetivo   : string en formato 'YYYY-MM' (ej: '2025-06')

    Retorna:
        df_consolidado con columna nueva: 'precio_indexado_YYYY-MM'
    """
    # ── Preparar tabla IPP: fecha → valor numérico ────────────
    df_ipp = df_ipp.copy()

    # Soportar tanto mayúsculas ('Fecha'/'IPP') como minúsculas ('fecha'/'ipp')
    col_fecha = next((c for c in df_ipp.columns if c.lower() == "fecha"), None)
    col_ipp   = next((c for c in df_ipp.columns if c.lower() == "ipp"), None)
    if col_fecha is None or col_ipp is None:
        raise ValueError(f"df_ipp debe tener columnas 'Fecha' e 'IPP'. Encontradas: {list(df_ipp.columns)}")

    df_ipp["fecha_ipp"] = pd.to_datetime(df_ipp[col_fecha]).dt.to_period("M").astype(str)
    mapa_ipp = dict(zip(df_ipp["fecha_ipp"], df_ipp[col_ipp]))

    # ── IPP del mes objetivo ──────────────────────────────────
    ipp_mes_obj = mapa_ipp.get(mes_objetivo)
    if ipp_mes_obj is None:
        raise ValueError(
            f"IPP para el mes objetivo '{mes_objetivo}' no encontrado. "
            f"Meses disponibles: {sorted(mapa_ipp.keys())}"
        )

    # ── Preparar columna IPP de origen ────────────────────────
    df_consolidado = df_consolidado.copy()

    # Buscar columna IPP en df_consolidado (puede llamarse 'IPP', 'ipp', 'Ipp', etc.)
    col_ipp_origen = next((c for c in df_consolidado.columns if c.lower() == "ipp"), None)
    if col_ipp_origen is None:
        raise ValueError(
            f"df_consolidado no tiene columna 'IPP'. "
            f"Columnas disponibles: {list(df_consolidado.columns)}"
        )

    # Convertir a 'YYYY-MM' para cruzar con mapa_ipp
    df_consolidado["fecha_ipp_origen"] = (
        pd.to_datetime(df_consolidado[col_ipp_origen], errors="coerce")
        .dt.to_period("M")
        .astype(str)
    )

    # Buscar IPP base por fila
    df_consolidado["IPP_base"] = df_consolidado["fecha_ipp_origen"].map(mapa_ipp)

    # ── Calcular precio indexado ──────────────────────────────
    col_indexada = f"precio_indexado_{mes_objetivo}"
    df_consolidado[col_indexada] = df_consolidado.apply(
        lambda x: (
            x["precio_oferta"] * (ipp_mes_obj / x["IPP_base"])
            if pd.notnull(x["IPP_base"]) else None
        ),
        axis=1,
    )

    # Limpiar columnas auxiliares
    df_consolidado = df_consolidado.drop(columns=["fecha_ipp_origen", "IPP_base"], errors="ignore")

    return df_consolidado


# ── Wrapper conveniente para el dashboard ────────────────────
def indexar_ofertas(df_ofertas: pd.DataFrame,
                    df_ipp: pd.DataFrame,
                    mes_objetivo: str) -> tuple[pd.DataFrame, str]:
    """
    Intenta indexar. Si la columna IPP no está disponible devuelve el
    DataFrame original y un mensaje de advertencia.

    Retorna:
        (df_resultado, col_precio)
        donde col_precio es 'precio_indexado_YYYY-MM' si tuvo éxito,
        o 'precio_oferta' si no fue posible indexar.
    """
    try:
        df_result = indexar_precios_por_mes(df_ofertas, df_ipp, mes_objetivo)
        col = f"precio_indexado_{mes_objetivo}"
        return df_result, col
    except ValueError as e:
        return df_ofertas.copy(), "precio_oferta"


def meses_disponibles(df_ipp: pd.DataFrame) -> list[str]:
    """Lista de meses 'YYYY-MM' disponibles en la serie IPP."""
    col_fecha = next((c for c in df_ipp.columns if c.lower() == "fecha"), df_ipp.columns[0])
    return sorted(
        pd.to_datetime(df_ipp[col_fecha], errors="coerce")
        .dt.to_period("M")
        .astype(str)
        .dropna()
        .unique()
        .tolist()
    )


def resumen_indexacion(df: pd.DataFrame, col_original: str, col_indexada: str) -> dict:
    """Estadísticas de la indexación para validación en UI."""
    mask = df[col_indexada].notna() & df[col_original].notna()
    if mask.sum() == 0:
        return {"n_indexados": 0, "n_sin_ipp": len(df), "factor_promedio": None}
    factor = (df.loc[mask, col_indexada] / df.loc[mask, col_original]).mean()
    return {
        "n_indexados":      int(mask.sum()),
        "n_sin_ipp":        int((~mask).sum()),
        "factor_promedio":  round(float(factor), 4),
        "precio_orig_prom": round(float(df.loc[mask, col_original].mean()), 2),
        "precio_idx_prom":  round(float(df.loc[mask, col_indexada].mean()), 2),
    }

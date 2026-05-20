# =============================================================
# api_client.py — Cliente para ms-olibia-pricing
# GET /v1/convocatorias reemplaza audiencias_master.xlsx
#
# Requiere red interna BIA o VPN.
# API key en variable de entorno BIA_API_KEY o en config/settings.yaml
# =============================================================

import os
import json
import time
import warnings
import pandas as pd

try:
    import requests
    _REQUESTS_OK = True
except ImportError:
    _REQUESTS_OK = False
import numpy as np
from pathlib import Path

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent
RAW  = ROOT / "data" / "raw"

# ── Configuración ─────────────────────────────────────────────
API_BASE    = "https://internal.bia.app/ms-olibia-pricing"
TIMEOUT_SEG = 20          # segundos para health check
TIMEOUT_ALL = 120         # segundos para descarga total (~75k filas)

# ── Leer API key ─────────────────────────────────────────────
def _get_api_key() -> str:
    """
    Orden de búsqueda:
    1. Variable de entorno  BIA_API_KEY
    2. config/settings.yaml  -> api.bia_key
    3. Archivo .env en raíz  -> BIA_API_KEY=...
    """
    # 1. Env
    key = os.environ.get("BIA_API_KEY", "")
    if key:
        return key

    # 2. settings.yaml
    try:
        import yaml
        cfg_path = ROOT / "config" / "settings.yaml"
        with open(cfg_path) as f:
            cfg = yaml.safe_load(f)
        key = cfg.get("api", {}).get("bia_key", "")
        if key and key != "TU_API_KEY_AQUI":
            return key
    except Exception:
        pass

    # 3. .env
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("BIA_API_KEY="):
                return line.split("=", 1)[1].strip()

    return ""


# ── Verificar conectividad ────────────────────────────────────
def api_disponible() -> bool:
    """True si la API interna de BIA es alcanzable."""
    if not _REQUESTS_OK:
        return False
    key = _get_api_key()
    if not key:
        return False
    try:
        r = requests.get(
            f"{API_BASE}/v1/health",
            headers={"X-Api-Key": key},
            timeout=TIMEOUT_SEG,
        )
        return r.status_code < 500
    except Exception:
        return False


# ── Descarga de convocatorias ─────────────────────────────────
def descargar_convocatorias(
    agente_comprador: str = None,
    adjudicadas: bool = None,
    delivery_start: str = None,
    delivery_end: str = None,
    verbose: bool = True,
) -> pd.DataFrame:
    """
    Llama a GET /v1/convocatorias y retorna un DataFrame raw.

    Parámetros opcionales (todos pueden omitirse para traer todo):
      agente_comprador : 'BIA', 'EPM', etc.  (ILIKE)
      adjudicadas      : True = solo adj, False = solo no adj, None = todas
      delivery_start   : 'YYYY-MM-DD'  (primer mes de entrega)
      delivery_end     : 'YYYY-MM-DD'  (último  mes de entrega)
    """
    key = _get_api_key()
    if not key:
        raise ValueError(
            "API key no encontrada. Configura BIA_API_KEY en .env "
            "o en config/settings.yaml bajo api.bia_key"
        )

    params = {}
    if agente_comprador:
        params["agente_comprador"] = agente_comprador
    if adjudicadas is not None:
        params["adjudicadas"] = "true" if adjudicadas else "false"
    if delivery_start:
        params["delivery_start"] = delivery_start
    if delivery_end:
        params["delivery_end"] = delivery_end

    if verbose:
        print(f"  Llamando {API_BASE}/v1/convocatorias  params={params}")
        t0 = time.time()

    r = requests.get(
        f"{API_BASE}/v1/convocatorias",
        headers={"X-Api-Key": key},
        params=params,
        timeout=TIMEOUT_ALL,
    )
    r.raise_for_status()

    data = r.json()

    # El API puede retornar lista directa o {"data": [...]}
    if isinstance(data, list):
        rows = data
    elif isinstance(data, dict):
        rows = data.get("data", data.get("items", data.get("convocatorias", [])))
    else:
        rows = []

    df = pd.DataFrame(rows)

    if verbose:
        elapsed = time.time() - t0
        print(f"  Recibidas: {len(df):,} filas  ({elapsed:.1f}s)")
        if len(df) > 0:
            print(f"  Columnas: {list(df.columns)}")

    return df


# ── Mapeo de campos API → formato interno ────────────────────
# Ajusta este mapa si el API usa nombres distintos.
# Ejecuta `python scripts/api_client.py --discover` para ver los nombres reales.

FIELD_MAP = {
    # API field               → nombre interno
    "announcement_code":      "audiencia_id",
    "codigo_convocatoria":    "audiencia_id",
    "conv":                   "audiencia_id",
    "agent_code":             "agente_codigo",
    "agente":                 "agente_codigo",
    "agent_short_name":       "agente_nombre",
    "agente_corto":           "agente_nombre",
    "offer_price":            "precio_oferta",
    "precio_oferta":          "precio_oferta",
    "quantity":               "cantidad_ofertada",
    "cantidad_oferta":        "cantidad_ofertada",
    "adjudicated_pct":        "pct_adjudicado",
    "porcentaje_adj":         "pct_adjudicado",
    "adjudicated":            "adjudicada",
    "adjudicada":             "adjudicada",
    "start_date":             "vigencia_inicio",
    "fecha_inicio_producto":  "vigencia_inicio",
    "end_date":               "vigencia_fin",
    "fecha_fin_producto":     "vigencia_fin",
    "curve_type":             "tipo_curva",
    "curva_plano":            "tipo_curva",
    "auction_date":           "fecha_audiencia",
    "audiencia_publica":      "fecha_audiencia",
    "AudienciaPublica":       "fecha_audiencia",
    "deadline_date":          "fecha_limite_oferta",
    "fecha_limite_oferta":    "fecha_limite_oferta",
    "FechaLimiteRecepcionOfertas": "fecha_limite_oferta",
    "buyer":                  "comprador",
    "agente_comprador":       "comprador",
    "market_type":            "tipo_mercado",
    "TipoMercado":            "tipo_mercado",
    "ipp":                    "ipp_fecha",
    "ipp_date":               "ipp_fecha",
}


def normalizar_respuesta(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aplica el FIELD_MAP al DataFrame crudo de la API y
    parsea fechas y numéricos.
    Retorna un DataFrame con las columnas internas estándar.
    """
    # Renombrar solo columnas que existen
    rename = {k: v for k, v in FIELD_MAP.items() if k in df.columns}
    df = df.rename(columns=rename)

    # Fechas
    for col in ["fecha_audiencia", "fecha_limite_oferta",
                "vigencia_inicio", "vigencia_fin", "ipp_fecha"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    # Numéricos
    for col in ["precio_oferta", "cantidad_ofertada", "pct_adjudicado"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Adjudicada → bool
    if "adjudicada" in df.columns:
        adj = df["adjudicada"]
        if adj.dtype != bool:
            df["adjudicada"] = adj.astype(str).str.strip().isin(
                ["true", "True", "TRUE", "1", "Sí", "SI", "si", "sí", "S"]
            )

    # pct_adjudicado: si no existe pero sí adjudicada
    if "pct_adjudicado" not in df.columns and "adjudicada" in df.columns:
        df["pct_adjudicado"] = df["adjudicada"].map({True: 100.0, False: 0.0})

    # tipo_curva limpio
    if "tipo_curva" in df.columns:
        df["tipo_curva"] = (
            df["tipo_curva"].astype(str).str.strip().str.upper()
            .replace({"NAN": "PLANO", "": "PLANO"})
        )

    return df


# ── Actualizar CSV desde API ──────────────────────────────────
def actualizar_ofertas_desde_api(verbose: bool = True) -> pd.DataFrame:
    """
    Descarga todas las convocatorias vía API, normaliza y guarda
    ofertas_por_agente_detalle.csv.
    Retorna el DataFrame resultante.
    """
    df_raw = descargar_convocatorias(verbose=verbose)
    df = normalizar_respuesta(df_raw)

    # Columnas calculadas que usa la app
    if "fecha_audiencia" in df.columns and "vigencia_inicio" in df.columns:
        df["horizonte_dias"] = (df["vigencia_inicio"] - df["fecha_audiencia"]).dt.days
    if "vigencia_inicio" in df.columns and "vigencia_fin" in df.columns:
        df["vigencia_anos"] = (
            (df["vigencia_fin"] - df["vigencia_inicio"]).dt.days / 365.25
        ).round(1)

    out = RAW / "ofertas_por_agente_detalle.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")
    if verbose:
        print(f"  [OK] Guardado: {out.name}  ({len(df):,} filas)")
    return df


# ── CLI: descubrir campos del API ─────────────────────────────
if __name__ == "__main__":
    import sys

    if "--discover" in sys.argv:
        print("Descubriendo campos del API...")
        # Pide solo 1 convocatoria para ver la estructura
        key = _get_api_key()
        if not key:
            print("ERROR: No se encontro BIA_API_KEY. Configura el .env primero.")
            sys.exit(1)

        try:
            r = requests.get(
                f"{API_BASE}/v1/convocatorias?codigo_convocatoria=CP-BIAC2022-001",
                headers={"X-Api-Key": key},
                timeout=30,
            )
            r.raise_for_status()
            data = r.json()
            rows = data if isinstance(data, list) else data.get(
                "data", data.get("items", data.get("convocatorias", [data]))
            )
            if rows:
                print("\nCampos del API:")
                for k, v in rows[0].items():
                    print(f"  {k!r:40s} -> {repr(v)[:60]}")
            else:
                print("Respuesta vacia")
        except Exception as e:
            print(f"Error: {e}")

    elif "--test" in sys.argv:
        print("Verificando disponibilidad...")
        ok = api_disponible()
        print("API disponible:", ok)
        if ok:
            print("\nDescargando muestra (1 convocatoria)...")
            df = descargar_convocatorias(agente_comprador="BIA")
            print(df.head(3).to_string())

    else:
        print("Uso:")
        print("  python scripts/api_client.py --discover  (ver campos del API)")
        print("  python scripts/api_client.py --test      (probar conectividad)")

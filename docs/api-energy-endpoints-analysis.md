# Análisis de Endpoints Energy — Herramienta de Oportunidad de Compra
*Para: Lucho (Tech) | Generado: Mayo 2026*

## Endpoints directamente útiles (reemplazan CSVs manuales)

### 1. `GET /energy/price/pb-min-avg-max` 🔴 Alta prioridad
- **Reemplaza:** `data/raw/pb_historica_diaria.csv`
- **Query:** `from: YYYY-MM-DD`, `to: YYYY-MM-DD`
- **Response:** `{ days: [{ date, min_pbna, avg_pbna, max_pbna }] }`
- **Mapeo de campos:** `min_pbna → pb_min_kwh`, `avg_pbna → pb_prom_kwh`, `max_pbna → pb_max_kwh`
- **Ganancia:** datos siempre frescos sin copiar archivos manualmente. Formato 1:1, cambio mínimo en `data_loader.py`.

### 2. `GET /energy/price/pb-forecast-hourly` 🔴 Alta prioridad
- **Reemplaza:** `data/raw/pronostico_pb_oficial.csv`
- **Query:** `from: YYYY-MM-DD`, `to: YYYY-MM-DD`
- **Response:** `{ points: [{ datetime, year, month, day, hour, p10, p50, p90 }] }`
- **Transformación:** agregar horas a día (promedio diario de p10/p50/p90)
- **Ganancia:** pronóstico siempre actualizado. El CSV actual tiene fechas fijas hasta enero 2027.

### 3. `GET /energy/price/monthly` 🟡 Media prioridad
- **Complementa:** cálculo de spread mensual en `master_con_pb.csv`
- **Query:** `from: YYYY-MM`, `to: YYYY-MM`
- **Response:** `{ months: [{ month, spot_price }] }`
- **Ganancia:** simplifica el cálculo de PB promedio mensual para el análisis de timing.

### 4. `GET /energy/price/pb-historical` 🟢 Baja prioridad
- **Reemplaza:** `pb_historica_diaria.csv` con granularidad horaria
- **Query:** `from: YYYY-MM-DD`, `to: YYYY-MM-DD`
- **Response:** `{ points: [{ datetime, year, month, day, hour, pb }] }`
- **Nota:** requiere agrupación a día en el loader. Usar `pb-min-avg-max` si solo se necesita diario.

---

## Endpoints para enriquecer la herramienta

### 5. `GET /energy/position/summary` 🟡 Media prioridad
- **Añade:** % cobertura actual (qué parte de la demanda ya está contratada vs expuesta a bolsa)
- **Query:** `month: YYYY-MM`, `market_type: regulated|non_regulated|both`
- **Response:** `{ coverage_pct, coverage_regulated_pct, coverage_non_regulated_pct, neto_bolsa_gwh, compras_bolsa_gwh, avg_buy_price_per_kwh }`
- **Uso:** si `coverage_pct` es bajo → mayor urgencia de abrir proceso. Input para la señal de compra en Home.

### 6. `GET /energy/demand/monthly` 🟡 Media prioridad
- **Añade:** cuánta energía necesita BIA por mes → cuánto hay que contratar
- **Query:** `from, to, market_type`
- **Response:** `{ chart: [{ month, regulated_gwh, non_regulated_gwh, total_gwh, total_estimated_gwh }] }`
- **Uso:** cruzar demanda proyectada con cobertura para calcular volumen a contratar.

### 7. `GET /energy/desviaciones/error-pb` 🟢 Baja prioridad
- **Añade:** calibración de confianza en el pronóstico de PB
- **Response incluye:** `pb_real_avg`, `pb_futura_avg`, `pb_estimado_gold_min/avg/max`
- **Uso:** mostrar historial de error del modelo para contextualizar la banda de incertidumbre en página Proyección PB.

---

## Endpoints que NO aplican

| Endpoint | Razón |
|---|---|
| `/energy/competitiveness/*` (9 endpoints) | Compara tarifas CU BIA vs comercializadores. Es para gestión comercial, no para compras en bolsa. |
| `/energy/desviaciones/summary`, `/error-demanda`, `/tarifa` | KPIs operativos internos. Para equipo de operaciones, no compras. |
| `/energy/position/hourly` | Granularidad horaria de posición. Overkill para decisiones estratégicas. |
| `/energy/demand/hourly-curve`, `/demand/daily` | Perfil de carga horario/diario. Más relevante para despacho. |
| `/energy/price/hourly-curve` | Curva horaria PB por tipo de día. Baja prioridad para esta herramienta. |

---

## Plan de integración sugerido

El cambio se hace en **`scripts/data_loader.py`** — reemplazar `pd.read_csv()` por `requests.get(API_URL + endpoint)`:

```python
# Ejemplo: reemplazar cargar_pb()
def cargar_pb() -> pd.DataFrame:
    resp = requests.get(f"{API_BASE}/energy/price/pb-min-avg-max",
                        params={"from": "2022-01-01", "to": date.today().isoformat()},
                        headers={"Authorization": f"Bearer {API_TOKEN}"})
    data = resp.json()
    df = pd.DataFrame(data["days"])
    df = df.rename(columns={"date": "fecha", "avg_pbna": "pb_prom_kwh",
                             "min_pbna": "pb_min_kwh", "max_pbna": "pb_max_kwh"})
    df["fecha"] = pd.to_datetime(df["fecha"])
    return df.sort_values("fecha").reset_index(drop=True)
```

Variables de entorno necesarias: `API_BASE` (URL base de la API), `API_TOKEN` (Bearer token).

---

## Estado actual de los archivos fuente

| Archivo CSV actual | Tamaño | Endpoint equivalente | Estado |
|---|---|---|---|
| `pb_historica_diaria.csv` | 91 KB | `/energy/price/pb-min-avg-max` | Manual |
| `pronostico_pb_oficial.csv` | 74 KB | `/energy/price/pb-forecast-hourly` | Manual |
| `master_con_pb.csv` | 173 KB | Sin equivalente directo (pipeline Colab) | Manual |
| `ofertas_por_agente_detalle.csv` | 216 KB | Sin equivalente (datos SICEP externos) | Manual |
| `ipp_serie.csv` | 1 KB | Sin equivalente (dato DANE) | Manual |

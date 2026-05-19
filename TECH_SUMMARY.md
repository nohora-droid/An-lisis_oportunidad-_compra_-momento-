# BIA Energy — Herramienta de Inteligencia de Compra
## Resumen Técnico para el Área de Tecnología

**Fecha:** Mayo 2026  
**Repositorio:** https://github.com/nohora-droid/An-lisis_oportunidad-_compra_-momento-.git  
**Entorno:** Python 3.13 · Streamlit · Local / LAN  
**Ejecutar:** doble clic en `arrancar_app.bat` → abre en `http://localhost:8501`

---

## 1. ¿Qué hace la herramienta?

Aplicación web multi-página para decisiones de compra de energía en el mercado regulado colombiano (SICEP). Responde tres preguntas de negocio:

1. **¿Cuándo abrir un proceso?** — Análisis de spread histórico precio adjudicado vs Precio de Bolsa (PB) por mes de audiencia.
2. **¿A quién comprarle?** — Perfil de cada generador: frecuencia de oferta, precios, tasa de adjudicación, horizonte de anticipación.
3. **¿Es buen momento ahora?** — Percentil histórico de la PB actual + señal de compra + pronóstico de bolsa a 9 meses.

---

## 2. Arquitectura

```
energy-buying-tool/
│
├── arrancar_app.bat              ← Lanzador Windows (streamlit run)
├── requirements.txt              ← Dependencias Python
│
├── app/
│   ├── main.py                   ← Entrada Streamlit: carga datos, sidebar global
│   └── pages/
│       ├── 1_Cuando_Comprar.py   ← Timing óptimo de contratación
│       ├── 2_Agentes.py          ← Perfil por generador / agente
│       ├── 3_Alertas_Mercado.py  ← Señal PB actual + histórico con zonas
│       ├── 4_Vendedores_Libres.py← Agentes no adjudicados (candidatos contacto)
│       ├── 5_Proyeccion_PB.py    ← Pronóstico PB base/húmedo/seco
│       └── 6_Precios_Vigencia.py ← Precios por año/mes de vigencia del contrato
│
├── scripts/
│   ├── data_loader.py            ← Carga y limpieza de todos los archivos fuente
│   ├── analisis.py               ← Funciones de análisis y métricas
│   └── indexador_ipp.py          ← Indexación de precios con serie IPP
│
├── data/
│   ├── raw/                      ← Archivos fuente (ver sección 3)
│   └── outputs/                  ← CSVs de resultados pre-calculados
│
└── config/
    └── settings.yaml             ← Parámetros configurables
```

**Patrón de datos entre páginas:**  
`main.py` carga todo al inicio con `@st.cache_data(ttl=3600)` y distribuye los DataFrames via `st.session_state`. Las páginas leen de session_state, nunca acceden directamente a disco (excepto fallback de pronóstico).

**Controles globales (sidebar):**
- Selector de **mes objetivo IPP** — todos los precios de todas las páginas se indexan al mes elegido.
- **Filtro de audiencias** — multiselect que filtra qué procesos se incluyen en los análisis.

---

## 3. Archivos fuente (`data/raw/`)

| Archivo | Tamaño | Filas | Descripción |
|---|---|---|---|
| `pb_historica_diaria.csv` | 91 KB | 1.581 | Precio de Bolsa diario TxF (ene 2022 – abr 2026). Cols: `fecha`, `pb_prom_kwh`, `pb_min_kwh`, `pb_max_kwh` |
| `ofertas_por_agente_detalle.csv` | 216 KB | 1.627 | Detalle de cada oferta presentada en audiencias SICEP. Cols: `audiencia_id`, `agente_nombre`, `precio_oferta`, `adjudicada`, `vigencia_inicio`, `vigencia_fin`, `horizonte_dias`, etc. 22 audiencias · 25 agentes · 27.9% tasa adjudicación |
| `master_con_pb.csv` | 173 KB | 353 | Un registro por proceso de compra con su contexto de PB. 46 columnas incluyendo: `precio_adj_prom`, `spread_vs_pb_30d`, `pb_relativa_90d`, `pb_tendencia`, `adjudicatario`, `comprador`, `horizonte_meses` |
| `ipp_serie.csv` | 1 KB | 46 | Serie IPP mensual jul 2022 – abr 2026. Cols: `fecha`, `ipp` (índice numérico) |
| `pronostico_pb_oficial.csv` | 74 KB | 276 (×9) | Pronóstico diario de PB abr 2026 – ene 2027. 9 filas por fecha: escenario base (p10/p50/p90) + húmedo (3 sims) + seco (3 sims) |
| `codigo_agentes.xlsx` | 3 KB | ~100 | Mapeo código SICEP → nombre largo → nombre corto del agente |

**Origen de los datos:**
- `pb_historica_diaria.csv` → **Metabase interno BIA** (tabla TxF)
- `ofertas_por_agente_detalle.csv` → procesado desde archivos `CP-*.xlsx` descargados de **SICEP/Drive** via `consolidador_total.py`
- `master_con_pb.csv` → cruce de procesos SICEP con PB (pipeline paso1 + paso2 Colab)
- `ipp_serie.csv` → **DANE / Drive** (Serie IPP Oferta Interna)
- `pronostico_pb_oficial.csv` → **Metabase interno BIA** (modelo de pronóstico)
- `codigo_agentes.xlsx` → **Google Drive** (carpeta Sicep insight)

---

## 4. Scripts Python

### `scripts/data_loader.py`
**Propósito:** carga y normaliza todos los archivos fuente. Punto único de acceso a datos.

```python
cargar_pb()         → DataFrame  # PB diaria + columnas año/mes/trim derivadas
cargar_ofertas()    → DataFrame  # Ofertas + horizonte_dias y vigencia_años calculados
cargar_master()     → DataFrame  # Procesos master con fechas parseadas
cargar_ipp()        → DataFrame  # Serie IPP (intenta CSV, luego Excel, luego sintético)
cargar_pronostico() → DataFrame  # Pronóstico: pivota base p10/p50/p90, promedia húmedo/seco
cargar_todo()       → dict       # Llama a las 5 funciones anteriores
```

Características:
- Detección automática de encoding (utf-8-sig → utf-8 → latin-1)
- `cargar_ipp()` tiene fallback: CSV → xlsx → serie sintética (no rompe si falta el archivo)
- `cargar_pronostico()` transforma 9 filas/día en 1 fila/día con columnas `base_p10`, `base_p50`, `base_p90`, `humedo_mean`, `seco_mean`

---

### `scripts/indexador_ipp.py`
**Propósito:** indexa precios de ofertas a un mes objetivo usando la serie IPP.

**Fórmula:**  
```
precio_indexado = precio_oferta × (IPP_mes_objetivo / IPP_mes_base_oferta)
```

Donde `IPP_mes_base_oferta` es la columna `IPP` de `audiencias_master.xlsx` — la fecha de referencia del precio de cada oferta (actualmente no disponible en `ofertas_por_agente_detalle.csv`, solo en `audiencias_master.xlsx`).

```python
indexar_precios_por_mes(df_consolidado, df_ipp, mes_objetivo)
    → df con columna nueva "precio_indexado_YYYY-MM"

indexar_ofertas(df_ofertas, df_ipp, mes_objetivo)
    → (df_resultado, nombre_columna_precio)   # wrapper con manejo de error

meses_disponibles(df_ipp)
    → list["YYYY-MM"]                         # meses con IPP disponible

resumen_indexacion(df, col_original, col_indexada)
    → dict {n_indexados, n_sin_ipp, factor_promedio, precio_orig_prom, precio_idx_prom}
```

---

### `scripts/analisis.py`
**Propósito:** funciones de análisis de negocio usadas por las páginas.

```python
analisis_timing(master, pb)
    → dict {por_mes, por_vigencia, pb_estacional}
    # spread histórico por mes de apertura, estacionalidad de PB

mejor_mes_para_vigencia(master, año_vigencia)
    → DataFrame  # meses rankeados por spread para un año de vigencia específico

proyectar_mejor_momento(master, pb, año_vigencia_objetivo)
    → dict {ranking_meses, recomendacion}

perfil_agentes(ofertas, pb, min_ofertas=3)
    → DataFrame  # resumen estadístico por agente

estacionalidad_agente(ofertas, agente)
    → Series  # cantidad de ofertas por mes del año

historial_agente(ofertas, agente)
    → DataFrame  # todas las ofertas de un agente

calcular_percentil_pb(pb, fecha_ref=None, ventana_hist_dias=1095)
    → dict {pb_actual, pb_30d, pb_90d, percentil, direccion, señal, tendencia_30d}
    # señal: "FUERTE ✅", "MODERADA ⚠️" o "ESPERAR 🔴"

alertas_vendedores_libres(ofertas, master, dias_ventana=90)
    → DataFrame  # agentes no adjudicados en la ventana, con precio y horizonte
```

---

### `app/main.py`
**Propósito:** página de inicio + orquestador global.

- Carga datos con `@st.cache_data(ttl=3600)` — se recalcula cada hora o al cambiar `version`.
- Distribuye DataFrames en `st.session_state` para que todas las páginas los consuman.
- **Sidebar global:** selector de mes IPP (con valor numérico), filtro de audiencias (multiselect), métricas de contexto.
- **Home:** métricas PB actuales, señal de compra, widget de pronóstico 30 días, últimos precios adjudicados, top 5 agentes.

---

### Páginas (`app/pages/`)

| Página | Archivo | Función principal |
|---|---|---|
| ⏱️ ¿Cuándo Comprar? | `1_Cuando_Comprar.py` | Spread adjudicado vs PB por mes de apertura. Filtro por año de vigencia. Proyección para año específico. Estacionalidad PB con banda P25-P75. |
| 🤝 Análisis de Agentes | `2_Agentes.py` | Tabla resumen por agente (n° ofertas, tasa adj, precio, horizonte). Perfil individual: estacionalidad, distribución de precios vs PB, historial. Comparador multi-agente. |
| 🔔 Alertas de Mercado | `3_Alertas_Mercado.py` | Percentil histórico de PB actual con señal verde/amarillo/rojo. Gráfica histórica con zonas de oportunidad (P25/P75) + procesos sobre la curva + pronóstico conectado. Análisis por zona de PB. |
| 📋 Vendedores Libres | `4_Vendedores_Libres.py` | Agentes no adjudicados en ventana configurable. Scatter precio vs horizonte (tamaño = frecuencia no adj.). Detalle de ofertas por proceso. |
| 🔮 Proyección PB | `5_Proyeccion_PB.py` | Histórico + pronóstico (banda P10-P90 base + líneas húmedo/seco). Vista mensual con tabla. Señal: PB proyectada vs PB actual. Identifica ventanas en meses históricamente favorables. |
| 📆 Precios por Vigencia | `6_Precios_Vigencia.py` | Precio ofertado vs adjudicado por año/mes de vigencia del contrato. Filtro de período de audiencias (1m, 3m, 6m, 1a, 2a, 3a, rango custom). Vistas anual y mensual con tabla detallada. |

---

## 5. Dependencias

```
Python          3.13
streamlit       ≥ 1.35   # Framework web
pandas          ≥ 2.0    # Manipulación de datos
numpy           ≥ 1.24   # Cálculos numéricos
plotly          ≥ 5.18   # Gráficas interactivas
openpyxl        ≥ 3.1    # Lectura de archivos .xlsx
scipy           ≥ 1.11   # (reservado para modelos estadísticos)
pyyaml          ≥ 6.0    # Lectura de config/settings.yaml
google-api-python-client  # Integración Google Drive (pendiente activar)
```

---

## 6. Cómo correr la aplicación

**Requisitos:** Python 3.10+ instalado, paquetes del `requirements.txt`.

```bash
# Instalar dependencias (una sola vez)
pip install -r requirements.txt

# Ejecutar
# Opción A — Windows: doble clic en arrancar_app.bat
# Opción B — terminal:
streamlit run app/main.py --server.port 8501
```

La app queda disponible en:
- Local: `http://localhost:8501`
- Red LAN: `http://192.168.30.43:8501` (cualquier usuario en la misma red)

---

## 7. Pendientes / Próximos pasos técnicos

| Ítem | Descripción | Prioridad |
|---|---|---|
| Pipeline consolidador | Adaptar `consolidador_total.py` y `consolidador_solicitado_drive.py` para correr localmente (hoy solo en Colab). Descargar `CP-*.xlsx` desde Drive, generar `audiencias_master.xlsx` con columna IPP. | Alta |
| Columna IPP en ofertas | `ofertas_por_agente_detalle.csv` no tiene la columna `IPP` (fecha base por oferta). Viene de `audiencias_master.xlsx`. Activar indexación real requiere ese archivo. | Alta |
| Actualización de datos | Hoy los datos se actualizan manualmente copiando CSVs. Implementar botón "Sincronizar con Drive" que descargue los archivos fuente via Google Drive API. | Media |
| Despliegue multi-usuario | Hoy corre en una sola máquina. Para acceso simultáneo de múltiples usuarios: desplegar en servidor (Streamlit Cloud, EC2, o servidor interno) con datos en Drive/S3. | Media |
| ConvocatoriasPublicas.xlsx | Archivo de metadata de procesos (69 KB en Drive). Necesario para el consolidador local. | Baja |

---

*Generado con Claude Code · BIA Energy S.A.S. E.S.P.*

# Dashboard Power BI — Mantenimiento Predictivo (NASA Turbofan)

Guía paso a paso para construir un dashboard ejecutivo sobre los datos del pipeline ETL.
Usa **Power BI Desktop** (gratuito): https://powerbi.microsoft.com/desktop/

**Para qué:** visualizar, por escenario (FD001-4), la salud de la flota de motores y
anticipar fallos. Cierra el ciclo *ETL → ML → BI* que piden las vacantes (Power BI, DAX,
dashboards ejecutivos).

---

## 0. Preparar los datos (ya hecho por el pipeline)
El script `src/add_predictions.py` unió train y test de los 4 escenarios, reconstruyó la
RUL real del test y agregó la predicción del modelo:

```
proyecto-etl-predictivo/data/curated/dashboard_data.parquet
```

Columnas disponibles: `id, cycle, op1-3, s1-21, rul, label, scenario, conjunto, rul_predicho, error`.
- `rul`  = ciclos restantes reales hasta falla (Remaining Useful Life).
- `rul_predicho` = predicción del modelo RandomForest (ciclos restantes).
- `error` = `rul_predicho - rul`.
- `label`= 1 si el motor fallará en ≤30 ciclos (riesgo inminente).
- `scenario` = FD001 … FD004 (para segmentar).
- `conjunto` = `train` / `test`. **Usa `test` para comparar real vs predicho de forma honesta**
  (train son predicciones en muestra, optimistas).

---

## 1. Conectar los datos
1. Abre **Power BI Desktop**.
2. Barra superior → **Obtener datos** → **Más…** → filtra por *Parquet* → **Archivo de Parquet** → **Conectar**.
3. Selecciona `data/curated/dashboard_data.parquet`.
4. En el editor previo (Power Query) verás las 28 columnas. Pulsa **Cargar**.

> Si prefieres la versión de ejemplo pequeña, usa `data/curated/sample_FD001_train.parquet`.

---

## 2. Medidas DAX (copiar y pegar)
En la cinta **Modelado** → **Nueva medida**. Pega cada una:

```DAX
Motores_Total = DISTINCTCOUNT(all_scenarios[id])
```

```DAX
RUL_Promedio = AVERAGE(all_scenarios[rul])
```

```DAX
%_Ciclos_Riesgo = DIVIDE( SUM(all_scenarios[label]), COUNTROWS(all_scenarios) )
```

```DAX
Motores_Riesgo =
CALCULATE(
    DISTINCTCOUNT(all_scenarios[id]),
    FILTER(all_scenarios, all_scenarios[rul] <= 30)
)
```

```DAX
RUL_Minimo = MIN(all_scenarios[rul])
```

```DAX
RMSE_RUL =
SQRT(
    DIVIDE(
        SUMX(all_scenarios, (all_scenarios[rul_predicho] - all_scenarios[rul]) ^ 2),
        COUNTROWS(all_scenarios)
    )
)
```

> Sustituye `all_scenarios` por el nombre real de tu tabla si Power BI lo renombró.

---

## 3. Visuales (lienzo)
Arrastra estos objetos desde el panel **Visualizaciones**:

### A. Tarjetas KPI (arriba)
- 4 visuales tipo **Tarjeta**: `Motores_Total`, `Motores_Riesgo`, `RUL_Promedio`, `%_Ciclos_Riesgo`.
- Formato → mostrar `%_Ciclos_Riesgo` como **porcentaje**.

### B. Degradación por motor (líneas)
- Visual **Líneas** → Eje X: `cycle`; Eje Y: `rul`; Leyenda: `id`.
- Filtra a 5-10 motores para legibilidad. Debe verse `rul` decreciendo hasta 0.

### C. Riesgo por escenario (barras)
- Visual **Barras agrupadas** → Eje X: `scenario`; Valores: `Motores_Riesgo` y `Motores_Total`.
- Muestra cuántos motores están en riesgo en cada uno de los 4 escenarios.

### D. Tabla "Top motores en riesgo"
- Visual **Tabla** → columnas: `scenario`, `id`, `cycle` (máx), `rul` (mín), `label`.
- Ordena por `rul` ascendente → los primeros son los más urgentes.

### E. Segmentación (filtros)
- Visual **Segmentación** → campo `scenario`.
- Opcional: otra segmentación por sensor (`s1`…`s21`) para explorar causas.

### F. Real vs Predicho (scatter)
- Visual **Gráfico de dispersión** → Eje X: `rul`; Eje Y: `rul_predicho`.
- Filtra `conjunto = test` (botón de filtro o segmentación) para una comparación honesta.
- Añade una línea de referencia `y = x` (muestra error 0). Cerca de la diagonal = buen modelo.
- Añade tarjeta **RMSE_RUL** para la métrica global de error.

---

## 4. Narrativa para tu portafolio / entrevista
> "El dashboard muestra la salud de una flota de motores de avión por escenario. Las KPIs
> indican cuántos motores están en riesgo inminente (RUL ≤ 30 ciclos) y el RUL promedio.
> El panel Real vs Predicho compara la RUL real contra la del modelo (RMSE ≈ 62 ciclos en
> test), lo que evidencia que el pipeline entrega datos y un modelo listos para producción.
> Esto permite al área de mantenimiento planificar reparaciones **antes** de la falla,
> pasando de mantenimiento correctivo (3-4× más caro) a **predictivo**, reduciendo paradas
> de línea y costos de piezas."

---

## 5. Siguiente nivel (opcional)
- Añadir columna `rul_predicho` desde `models/modelo_rul.joblib` para comparar real vs predicho.
- Publicar en **Power BI Service** y programar actualización vía gateway.
- Conectar el origen a **S3 / Athena** en vez de Parquet local (nivel nube AWS).

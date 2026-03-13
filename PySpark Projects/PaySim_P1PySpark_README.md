# 🏦 Detección de Fraude en Transacciones Móviles (PaySim) con PySpark

Este proyecto implementa un pipeline completo de análisis de datos y Machine Learning utilizando **PySpark** para detectar transacciones fraudulentas en un ecosistema de pagos móviles. El análisis se basa en el dataset sintético **PaySim**, que simula transacciones reales para la investigación de fraudes.

## 🚀 Descripción del Proyecto

El objetivo principal es identificar patrones de comportamiento fraudulentos, tales como transferencias sospechosas y retiros de efectivo inusuales, utilizando técnicas de ingeniería de características y modelos de clasificación.

### 🛠️ Tecnologías Utilizadas
*   **PySpark:** Procesamiento de datos a gran escala y Spark MLlib.
*   **Java 21:** Motor de ejecución de Spark (configurado para compatibilidad).
*   **Python 3.14:** Lenguaje de scripting.
*   **Pandas & Matplotlib:** Visualización de resultados e informes finales.

---

## ⚙️ Configuración del Entorno (Windows)

Debido a requisitos específicos de compatibilidad entre Spark y las versiones modernas de Java en Windows, el proyecto incluye una configuración inicial crítica para evitar errores de `unicodeescape` y `getSubject`:

```python
import os
# Forzar el uso de Java 21 para evitar errores de compatibilidad con Java 25
os.environ["JAVA_HOME"] = r"C:\Program Files\Java\jdk-21.0.10"
```

---

## 📊 Pipeline de Datos

1.  **Carga y Limpieza:** Lectura de datos desde CSV con definición de esquema estricta (`StructType`).
2.  **Ingeniería de Características:**
    *   `errorBalanceOrig`: Detecta discrepancias en el saldo de origen después de la transacción.
    *   `errorBalanceDest`: Detecta discrepancias en el saldo de destino.
    *   `avg_prev_amount`: Calcula el promedio histórico de transacciones por usuario mediante **Window Functions**.
3.  **Transformación:** Vectorización de características usando `VectorAssembler` e indexación de tipos categóricos con `StringIndexer`.

---

## 🤖 Modelo de Machine Learning

Se utilizó un algoritmo de **Random Forest Classifier** obteniendo resultados de alto rendimiento:

*   **Área bajo la curva (AUC-ROC):** ~0.9984 (Excelente precisión).
*   **Recall (Sensibilidad):** Captura la vasta mayoría de los fraudes reales.
*   **Variables clave:** Las discrepancias de balance (`errorBalance`) resultaron ser los factores más predictivos.

---

## 💰 Impacto Económico

El modelo evalúa el éxito basándose en el capital protegido:

*   **Dinero Salvado:** Capital total de fraudes detectados y bloqueados.
*   **Riesgo de Fuga:** Monto asociado a fraude no detectado (Falsos Negativos).
*   **Eficiencia por Monto:** Indica el porcentaje del capital total que el sistema logra proteger.

---

## 📈 Cómo ejecutar
1.  Asegúrate de tener instalado **PySpark** y **Java 21/17**.
2.  Coloca el dataset `PS_20174392719_1491204439457_log.csv` en la carpeta del proyecto.
3.  Asegúrate de que las rutas en el código usen el prefijo `r''` (raw strings) para evitar errores de Windows.
4.  Ejecuta las celdas secuencialmente en el Jupyter Notebook.

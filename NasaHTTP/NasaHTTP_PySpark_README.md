# 🚀 Análisis de Logs de Servidores NASA con PySpark

Este proyecto implementa un pipeline de **Ingeniería de Datos** y **Análisis de Seguridad** utilizando PySpark para procesar y extraer inteligencia de más de 1.5 millones de registros de acceso del servidor HTTP de la NASA (1995).

## 🎯 Objetivo del Proyecto
El fin principal es transformar datos no estructurados (.log) en información accionable para identificar:
1.  **Seguridad:** Detección de posibles ataques o bots mediante el análisis de errores (4xx, 5xx).
2.  **Rendimiento:** Identificación de picos de tráfico por hora para optimización de servidores.
3.  **Contenido:** Determinación de los recursos y páginas más populares.

---

## 🛠️ Tecnologías y Configuración
*   **PySpark:** Procesamiento distribuido de grandes volúmenes de datos.
*   **Regex (Expresiones Regulares):** Técnica avanzada para estructurar texto plano.
*   **Java 21:** Configurado específicamente para compatibilidad en entornos Windows.
*   **Pandas:** Utilizado para la exportación final de reportes limpios y cuadros de mando.

### Configuración Crítica (Windows)
```python
import os
# Solución a incompatibilidad de Java en Windows
os.environ["JAVA_HOME"] = r"C:\Program Files\Java\jdk-21.0.10"
# Configuración para evitar errores de casteo en datos sucios
spark.conf.set("spark.sql.ansi.enabled", "false")
```

---

## 📊 Flujo de Trabajo (Pipeline)

1.  **Ingesta:** Carga de datos brutos desde `access.log`.
2.  **Estructuración (Parsing):** Aplicación de un patrón Regex robusto para extraer IP, Timestamp, Método, Endpoint, Código de Estado y Tamaño.
    *   *Patrón utilizado:* `r'^(\S+) - - \[(.*?)\] "(.*?) (.*?) (.*?)" (\d{3}) (\d+|-)'`
3.  **Limpieza:** Uso de `try_cast` y filtros de integridad para eliminar líneas malformadas o vacías que suelen corromper los archivos log.
4.  **Análisis:**
    *   Filtros para códigos de error `>= 400`.
    *   Funciones de ventana y manipulación de cadenas para extraer la hora (`hour`).
5.  **Exportación:** Generación de archivos CSV profesionales sobreescritos en cada ejecución.

---

## 📈 Hallazgos y Resultados Exportados

El proyecto genera automáticamente los siguientes reportes en la carpeta raíz:
*   `nasa_logs_estructurados_FULL.csv`: El dataset completo procesado y listo para cualquier herramienta de BI.
*   `reporte_seguridad_ips.csv`: Ranking de las IPs con mayor tasa de fallos (auditoría de ataques).
*   `reporte_trafico_hora.csv`: Distribución temporal del tráfico (análisis de carga).
*   `reporte_paginas_visitadas.csv`: Inventario de los recursos más solicitados.

---

## 💡 Conclusión Técnica
Este trabajo demuestra la capacidad de **PySpark** para manejar el "vicio" de los archivos log (datos no estructurados) y convertirlos en una base de datos relacional eficiente, superando las limitaciones de herramientas convencionales como Excel ante archivos de gran volumen.

{# ---------------------------------------------------------------------------
   Trino 442 NO trae INITCAP ni TITLE_CASE (si existen en Spark, Hive y Postgres).
   Este macro implementa "title case" con funciones 100% soportadas por Trino:

       split()      -> parte el texto en palabras
       transform()  -> aplica una funcion lambda a cada palabra
       array_join() -> vuelve a unir las palabras

   Uso:  {{ title_case('customer_city') }}
   --------------------------------------------------------------------------- #}

{% macro title_case(column_name) -%}
array_join(
    transform(
        split(lower(trim({{ column_name }})), ' '),
        w -> upper(substr(w, 1, 1)) || substr(w, 2)
    ),
    ' '
)
{%- endmacro %}

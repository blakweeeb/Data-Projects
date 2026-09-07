{#
  En Trino el "schema" es realmente <catalogo>.<esquema>.
  Queremos controlar el esquema de destino (staging / lakehouse) tal cual,
  sin que dbt concatene el schema del perfil.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}

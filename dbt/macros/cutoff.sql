{% macro cutoff() %}
  {% set value = var('as_of') %}
  {% set parsed = modules.datetime.datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ') %}
  '{{ parsed.strftime('%Y-%m-%dT%H:%M:%SZ') }}'
{% endmacro %}

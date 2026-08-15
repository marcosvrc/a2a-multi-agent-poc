# ADR-006 — OpenTelemetry como padrão de observabilidade

## Status
Aceito

## Contexto
Todas as chamadas importantes devem ter `trace_id`, `correlation_id` e
logs estruturados (PROJECT_SPEC.md §1, item 6, e §24).

## Decisão
Cada agente Python instrumenta FastAPI com
`opentelemetry-instrumentation-fastapi`, exporta traces via OTLP gRPC para
o `otel-collector`, que encaminha para o Jaeger. Logs são JSON estruturado
e incluem `trace_id`/`span_id` quando disponíveis (`app/telemetry.py`).

## Consequências
- `OTEL_SDK_DISABLED=true` é usado nos testes automatizados para evitar
  threads de exportação tentando conectar a um collector inexistente.

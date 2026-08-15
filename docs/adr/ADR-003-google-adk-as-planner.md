# ADR-003 — Google ADK como framework do Planner

## Status
Aceito (implementação de orquestração determinística nesta milestone)

## Contexto
PROJECT_SPEC.md §5.1 define o Planner Agent como orquestrador global,
implementado em Google ADK / Python.

## Decisão
`agents/planner-adk` declara `google-adk` como dependência. Nesta
milestone (M1), a orquestração é determinística (sem chamada a LLM), para
validar apenas o transporte A2A e manter RNF-03 (custo zero por padrão)
enquanto nenhum especialista real existe ainda. A camada de raciocínio via
ADK (seleção de agentes, fan-out orientado por LLM) será introduzida a
partir da Fase 6, quando houver múltiplos especialistas reais para
orquestrar em paralelo.

## Consequências
- O Planner já expõe Agent Card, discovery via Registry e o esqueleto de
  estados (§12), prontos para receber a camada ADK sem mudar o contrato
  HTTP/A2A externo.

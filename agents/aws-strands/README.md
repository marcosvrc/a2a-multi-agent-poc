# aws-enrichment-agent

Agente de enriquecimento (Strands Agents SDK, Python), conforme
`PROJECT_SPEC.md` §5.6. Totalmente **opcional**: o sistema inteiro
funciona sem ele. Responsabilidade reduzida — só weather commentary e
destination tips curtas. Nunca aprova/rejeita viagem, calcula orçamento
final, ou escolhe hotel/voo, e nunca bloqueia o Planner.

## Ligar/desligar

O Planner só chama este agente quando `AWS_AGENT_ENABLED=true`
(env var lida pelo Planner, não por este agente). Com `false` (padrão),
o Planner nem tenta descobrir/chamar o skill `enrich_destination` —
`enrichment.status` vem `SKIPPED` na resposta, e isso nunca é tratado
como falha (§11 "AWS Enrichment indisponível: Ignorar").

## Dois caminhos de execução

- **Determinístico (padrão, sem `MODEL_PROVIDER` ou valor desconhecido)**:
  `weather_summary` vem de uma chamada real ao `mcp-weather` (mesma
  ferramenta que o Activity Agent já usa); `destination_tips` vem de uma
  tabela fixa de dicas por tag de preferência do viajante, mais uma dica
  genérica com o destino no template. Nada aqui finge ser uma
  recomendação gerada por IA — é o caminho testado automaticamente e o
  que roda em `docker compose up` sem custo.
- **Guiado por Strands (`MODEL_PROVIDER=ollama` ou `MODEL_PROVIDER=bedrock`)**:
  usa o AWS Strands Agents SDK com um modelo local (Ollama) ou Amazon
  Bedrock para gerar comentário de clima e dicas. O forecast em si ainda
  vem do `mcp-weather` real — o modelo só transforma isso em texto, nunca
  inventa a previsão (§31). Ver ADR-013. Não é exercitado pelos testes
  automatizados desta milestone (nenhum Ollama/Bedrock real em CI/dev por
  padrão); qualquer falha cai automaticamente para o determinístico.

## Modos (§5.6)

```text
Local:    Strands -> Ollama
AWS Lite: Strands -> Amazon Bedrock
AWS Full: A2A -> Amazon Bedrock AgentCore Runtime -> Strands -> Amazon Bedrock (futuro)
```

`AgentCore` é evolução opcional, não requisito desta milestone.

## Skill

```text
enrich_destination
```

## Endpoints

- `GET /health`, `GET /ready`
- `GET /.well-known/agent-card.json`
- `POST /a2a` (A2A JSON-RPC, mesmo adapter dos outros agentes Python)

## Rodando localmente

```bash
pip install -e .
uvicorn app.main:app --reload --port 8006
```

Para o caminho Strands (opcional):

```bash
pip install -e ".[strands]"
MODEL_PROVIDER=ollama OLLAMA_HOST=http://localhost:11434 uvicorn app.main:app --reload --port 8006
```

## Testes

```bash
pip install -e . pytest
pytest -q
```

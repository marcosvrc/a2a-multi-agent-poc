#!/usr/bin/env bash
# Smoke test for Milestone M1 (PROJECT_SPEC.md §36).
# Assumes the stack is already running (`make local` or `docker compose up`).
set -euo pipefail

REGISTRY_URL="${REGISTRY_URL:-http://localhost:8080}"
PLANNER_URL="${PLANNER_URL:-http://localhost:8001}"
JAEGER_URL="${JAEGER_URL:-http://localhost:16686}"

step() { echo "==> $1"; }

step "1. Verificando Agent Registry ($REGISTRY_URL)"
curl -sf "$REGISTRY_URL/health" > /dev/null

step "2. Verificando Agent Cards dos agentes registrados"
AGENTS_JSON=$(curl -sf "$REGISTRY_URL/agents")
echo "$AGENTS_JSON" | python3 -c "
import json, sys, urllib.request
agents = json.load(sys.stdin)
for a in agents:
    url = a['agent_card_url']
    with urllib.request.urlopen(url, timeout=5) as resp:
        card = json.load(resp)
        assert 'skills' in card and card['skills'], f'{a[\"id\"]} has no skills'
        print(f\"  ok: {a['id']} -> {card['name']}\")
"

step "3. Verificando health de cada agente via Registry"
echo "$AGENTS_JSON" | python3 -c "
import json, sys
agents = json.load(sys.stdin)
print('agents to check:', [a['id'] for a in agents])
"
for id in $(echo "$AGENTS_JSON" | python3 -c "import json,sys;print(' '.join(a['id'] for a in json.load(sys.stdin)))"); do
  curl -sf "$REGISTRY_URL/agents/$id/health" > /dev/null && echo "  ok: $id"
done

step "4. Verificando Planner ($PLANNER_URL)"
curl -sf "$PLANNER_URL/health" > /dev/null
curl -sf "$PLANNER_URL/.well-known/agent-card.json" > /dev/null

step "5. Enviando solicitação de viagem de teste"
RESPONSE=$(curl -sf -X POST "$PLANNER_URL/v1/travel-requests" \
  -H 'Content-Type: application/json' \
  -d '{
    "origin": "Sao Paulo",
    "destination": "Florianopolis",
    "start_date": "2026-09-20",
    "end_date": "2026-09-24",
    "travelers": 2,
    "budget": 8000,
    "currency": "BRL",
    "preferences": ["beach", "gastronomy", "outdoor"]
  }')

step "6. Validando resposta JSON e request_id"
echo "$RESPONSE" | python3 -c "
import json, sys
body = json.load(sys.stdin)
assert body.get('request_id'), 'missing request_id'
assert body.get('status') in ('COMPLETED', 'PARTIAL', 'FAILED'), 'unexpected status'
assert body.get('metadata', {}).get('trace_id'), 'missing trace_id'
print('  request_id:', body['request_id'])
print('  status:', body['status'])
print('  trace_id:', body['metadata']['trace_id'])
"

step "7. Verificando A2A round-trip (foundation check)"
curl -sf "$PLANNER_URL/v1/foundation-check" | python3 -c "
import json, sys
body = json.load(sys.stdin)
print('  discovered_agents:', body['discovered_agents'])
print('  status:', body['status'])
"

step "8. Jaeger UI disponível em:"
echo "  $JAEGER_URL"

echo
echo "SMOKE TEST OK"

"""Captura paga explícita de respostas com prompts fictícios e orçamento controlado.

Executar em backend/: LLM_MODE=featherless .venv/bin/python scripts/record_demo.py --capture
"""

import argparse
import asyncio
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.budget import estimate_call_cost  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.llm import generate  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402

SCENARIOS = [
    ("router.commercial", "router", "Qwen/Qwen3.5-4B", 48,
     "Roteador: dúvidas de estadia = commercial_node1; defeito ou conserto = maintenance_node2. "
     "Retorne apenas o identificador da categoria, sem explicação ou formatação.",
     "Olá, gostaria de tirar dúvidas sobre a estadia."),
    ("router.maintenance", "router", "Qwen/Qwen3.5-4B", 48,
     "Roteador: dúvidas de estadia = commercial_node1; defeito ou conserto = maintenance_node2. "
     "Retorne apenas o identificador da categoria, sem explicação ou formatação.",
     "Há um vazamento na cozinha e preciso de conserto."),
    ("commercial.greeting", "commercial_node1", "Qwen/Qwen3.5-9B", 256,
     "Você é o Assistente Zelo. Responda à saudação em uma frase curta, simpática, "
     "sem emojis ou Markdown, perguntando como pode ajudar. Não presuma uma reserva.", "Olá!"),
    ("commercial.unavailable", "commercial_node1", "Qwen/Qwen3.5-9B", 256,
     "Na demonstração gravada você não tem confirmação da informação pedida. Diga em uma "
     "frase curta que a informação precisa ser confirmada com o anfitrião. "
     "Não mencione uma comodidade, imóvel, número ou detalhe específico. Sem Markdown.",
     "Pode me dar uma informação que não está cadastrada?"),
    ("validator_node2", "validator_node2", "Qwen/Qwen3.5-4B", 256,
     "Confirme brevemente o recebimento do relato de manutenção, sem inventar categoria, "
     "preço, data ou contratação. Sem Markdown.", "Relato de problema no imóvel recebido."),
    ("resolver_adm_summary", "resolver_adm_summary", "Qwen/Qwen3.5-9B", 320,
     "Escreva uma orientação curta e neutra para o anfitrião comparar os orçamentos "
     "exibidos na tela e escolher o prestador. Não escolha por ele nem invente nomes, "
     "valores, quantidade, datas ou serviços. Não afirme ter notificado o hóspede.",
     "Os orçamentos recebidos estão nos cartões da interface."),
    ("resolver_notify_tenant", "resolver_notify_tenant", "Qwen/Qwen3.5-4B", 160,
     "Redija uma frase curta avisando o hóspede da visita de manutenção confirmada. "
     "Inclua literalmente os dois marcadores {{service}} e {{scheduled_date}}, "
     "sem alterar os marcadores, sem Markdown e sem dados adicionais.",
     "Serviço: {{service}}. Data/Hora: {{scheduled_date}}."),
    ("scraper_nodeS", "scraper_nodeS", "Qwen/Qwen3.5-4B", 64,
     "Classifique confirmação explícita de contato. Responda apenas JSON com confirmed "
     "booleano; dúvida é false.", "Talvez, ainda preciso verificar."),
]


async def capture() -> None:
    if settings.llm_mode != "featherless" or settings.featherless_api_key in ("", "mock-key"):
        raise SystemExit("A captura exige LLM_MODE=featherless e uma chave configurada.")
    run_id = f"recorded-demo-capture-{uuid4().hex[:8]}"
    path = Path(__file__).resolve().parents[1] / "app/demo/recordings.json"
    responses = json.loads(path.read_text())["responses"] if path.exists() else {}
    estimate = sum(
        estimate_call_cost(model, (len(system) + len(user)) // 4, tokens)
        for _, _, model, tokens, system, user in SCENARIOS
    )
    if estimate > 0.003:
        raise SystemExit("Estimativa de captura excede o teto adicional de US$ 0,003.")
    print(f"Captura {run_id}: 8 chamadas, estimativa US$ {estimate:.6f}.", flush=True)
    with SessionLocal() as db:
        for key, node, model, tokens, system, user in SCENARIOS:
            messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
            prompt_hash = hashlib.sha256(json.dumps(messages).encode()).hexdigest()
            if responses.get(key, {}).get("prompt_sha256") == prompt_hash:
                print(f"Gravação existente preservada: {key}", flush=True)
                continue
            response = await generate(
                messages, model, tokens, run_id=run_id, node=node, temperature=0.1, db=db,
            )
            content = response.content.strip()
            if not content:
                raise SystemExit(f"Resposta vazia em {key}; nenhuma gravação publicada.")
            if key.startswith("router."):
                expected = (
                    "maintenance_node2" if key.endswith("maintenance") else "commercial_node1"
                )
                if content.strip("`'\" \n.") != expected:
                    raise SystemExit(f"Classificação inesperada em {key}: {content!r}.")
            if key == "resolver_notify_tenant" and not all(
                marker in content for marker in ("{{service}}", "{{scheduled_date}}")
            ):
                raise SystemExit("Modelo não preservou os marcadores do aviso.")
            if key == "scraper_nodeS" and json.loads(content) != {"confirmed": False}:
                raise SystemExit("Confirmação ambígua não pode ser positiva.")
            responses[key] = {
                "node": node, "model": model, "content": content,
                "captured_at": datetime.now(UTC).isoformat(),
                "source": "featherless", "capture_run_id": run_id,
                "prompt_sha256": prompt_hash,
                "capture_input_tokens": response.input_tokens,
                "capture_output_tokens": response.output_tokens,
                "capture_cost_usd": response.cost_usd,
                "messages": messages,
            }
            path.write_text(json.dumps({"version": 1, "responses": responses},
                                       ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"Gravado: {key}", flush=True)
    print(f"Captura concluída: US$ {sum(r['capture_cost_usd'] for r in responses.values()):.8f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", action="store_true", required=True,
                        help="Autoriza a captura paga explícita; não é usado na reprodução.")
    parser.parse_args()
    asyncio.run(capture())

# Status do Projeto — Fonte da Verdade (`STATUS.md`)

Atualizado em: `2026-11-07` (alinhado ao `planejamento2.md`).

Estados permitidos: **não iniciada** | **em andamento** | **em revisão** | **aprovada** | **bloqueada**.
Todo agente deve ler este arquivo antes de iniciar qualquer ação e atualizá-lo ao iniciar e ao concluir seu trabalho.

---

## 1. Visão por Fase

| Fase | Estado | Responsável | Branch Atual | Último Commit | Bloqueios / Decisões Confirmadas |
| --- | --- | --- | --- | --- | --- |
| **Planejamento** | **aprovada** | Orquestrador → Planejador / Revisor | `main` / `develop` | — | Escopo v2 consolidado (`planejamento2.md`) e Gate S0 aprovado. |
| **Implementação** | **em andamento** | Dev 1–4 + Implementador | `develop` | — | Iniciada a partir de `develop`. Desenvolvimento inicial 100% com mocks/simulações. |
| **Validação** | **não iniciada** | Dev 1–4 + Revisor | — | — | Reserva obrigatória de US$ 7,50 (30% dos US$ 25 da Featherless) preservada para os testes finais com modelos reais, ensaio e Demo Day. |

---

## 2. Sprints e Tasks

| Sprint / Task | Fase | Estado | Responsável (Dev + Agente) | Branch Prevista | Último Commit | Dependências / Observações |
| --- | --- | --- | --- | --- | --- | --- |
| **S0-T0** Planejamento v2 e Gate S0 | Planejamento | **aprovada** | Dev 1 + Planejador / Revisor | `main` / `develop` | — | Sem bloqueios de arquitetura; decisões de `planejamento2.md` aplicadas. |
| **S1-T1** PostgreSQL, Modelos SQL e Contratos Pydantic v2 | Implementação | **aprovada** | Dev 1 + Implementador / Revisor | `feature/s1-t1-db-contracts` | `0afa816` | Postgres, modelos SQLAlchemy 2.0, schemas Pydantic v2 com run_id e seed concluídos e auditados (97.6% cobertura). |
| **S1-T2** Cliente LLM (Mock/Featherless), Custo, Guardrails, LGPD e Langfuse | Implementação | **não iniciada** | Dev 3 + Implementador / Revisor | `feature/s1-t2-llm-cost-security` | — | Depende de S1-T1. Inclui mascaramento LGPD e envio de custo ao Langfuse. |
| **S1-T3** Fluxo B — Nó S (Coletor/Validador Periódico via APScheduler) | Implementação | **não iniciada** | Dev 4 + Implementador / Revisor | `feature/s1-t3-node-s-scheduler` | — | Depende de S1-T1, S1-T2. Grava apenas prestadores que confirmaram contato. |
| **S1-T4** Shell Frontend Estilo Airbnb (Imóveis, Chat Único e Sessão ADM) | Implementação | **não iniciada** | Dev 2 + Implementador / Revisor | `feature/s1-t4-frontend-airbnb-shell` | — | Depende de S0-T0 (paralela à S1-T1). Cria `frontend/` do zero em React + TS. |
| **S2-T5** Roteador Barato + Nó 1 (Comercial) + Nó 2 (Validador) | Implementação | **não iniciada** | Dev 1 + Implementador / Revisor | `feature/s2-t5-router-node1-node2` | — | Depende de S1-T1, S1-T2. Chat único roteia dúvida → Nó 1 e problema → Nó 2. |
| **S2-T6** Fluxo C — Nó 3 (Resolvedor em LangGraph + Urgência × Agenda) | Implementação | **não iniciada** | Dev 3 + Implementador / Revisor | `feature/s2-t6-node3-langgraph-resolver` | — | Depende de S1-T1, S1-T2, S1-T3. Implementa os 5 passos, `interrupt` ADM e loops. |
| **S2-T7** Integração Frontend (Sessão Agente ⇄ Anfitrião + Simulador) | Implementação | **não iniciada** | Dev 2 + Implementador / Revisor | `feature/s2-t7-frontend-integration` | — | Depende de S1-T4, S2-T5, S2-T6. Conecta UI às APIs e aprovação humana. |
| **S2-T8** Testes de Integração (Caminhos Alternativos) e Suíte de Segurança | Validação | **não iniciada** | Dev 4 + Implementador / Revisor | `feature/s2-t8-integration-security-tests` | — | Depende de S2-T5, S2-T6. Cobre timeouts, recusa de data, sem prestador e injection. |
| **S3-T9** Testes E2E com Modelos Reais (Featherless) e Recalibração de Custo | Validação | **não iniciada** | Dev 1 + Implementador / Revisor | `fix/s3-t9-real-llm-e2e` | — | Depende de S2 concluída. Ativa modelos reais pagos e atualiza `docs/COST.md`. |
| **S3-T10** Deploy do Link Testável + Seed/Reset para Avaliadores | Validação | **não iniciada** | Dev 2 + Implementador / Revisor | `feature/s3-t10-deploy-link` | — | Depende de S2 concluída. |
| **S3-T11** Roteiro, Gravação do Vídeo e Material do Pitch (Demo Day) | Validação | **não iniciada** | Dev 3 + Implementador / Revisor | `docs/s3-t11-pitch-video` | — | Depende de S2 concluída. |
| **S3-T12** Pacote Final de Submissão e Plano B (`recorded_demo`) | Validação | **não iniciada** | Dev 4 + Implementador / Revisor | `docs/s3-t12-submission-plan-b` | — | Depende de S3-T9, S3-T10, S3-T11. |

---

## 3. Decisões Confirmadas e Diretrizes Ativas

1. **Orçamento e Estratégia Mock-First:** Os US$ 25,00 na Featherless são exclusivos para os agentes de negócio do produto (reserva obrigatória de 30% = US$ 7,50 para a S3; teto de US$ 17,50 antes disso). Durante o desenvolvimento e testes de unidade/integração, usa-se `LLM_MODE=mock`; os modelos reais entram na etapa final.
2. **Arquitetura de 3 Fluxos + Roteador de Chat Único:**
   - Ponto único de chat no imóvel com roteador barato (`dúvida → Nó 1` / `problema de inquilino ou camareira → Nó 2`).
   - **Fluxo A (Aquisição):** Nó 1 atende até a reserva confirmada ("temos inquilino").
   - **Fluxo B (Coleta Periódica):** Nó S roda via `APScheduler`, valida contato dos prestadores e salva apenas os confirmados no PostgreSQL.
   - **Fluxo C (Manutenção):** Nó 2 gera ticket Pydantic → Nó 3 (LangGraph) pede orçamentos (sem negociar preço) → notifica o ADM na **sessão Agente ⇄ Anfitrião do imóvel** → ADM escolhe o prestador → Nó 3 propõe data conforme **urgência × agenda** → prestador confirma (se recusar, volta ao passo 3) → avisa inquilino se estiver hospedado.
3. **Stack Técnica:** Python 3.12, FastAPI, Pydantic v2, LangGraph (no Nó 3), APScheduler, PostgreSQL, React + TypeScript, Langfuse, cobertura mínima de **70% no código novo**.
4. **Desafio Tako:** Não concorre (foco 100% em imóveis de temporada).
5. **LGPD:** Telefones de prestadores e dados pessoais de hóspedes ficam apenas no PostgreSQL e são mascarados antes de logs e traces do Langfuse.

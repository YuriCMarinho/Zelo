# Status do Projeto — Fonte da Verdade (`STATUS.md`)

Atualizado em: `2026-11-07` (alinhado a `docs/PLAN.md` como fonte única da verdade).

Estados permitidos: **não iniciada** | **em andamento** | **em revisão** | **aprovada** | **bloqueada**.
**Versão canônica: a de `develop`.** As cópias em `main` e nas branches de task podem estar defasadas; leia sempre `git show origin/develop:docs/STATUS.md`.
Todo agente deve ler este arquivo antes de iniciar qualquer ação e atualizá-lo ao iniciar e ao concluir seu trabalho.

---

## 1. Visão por Fase

| Fase | Estado | Responsável | Branch Atual | Último Commit | Bloqueios / Decisões Confirmadas |
| --- | --- | --- | --- | --- | --- |
| **Planejamento** | **aprovada** | Orquestrador → Planejador / Revisor | `main` / `develop` | — | Escopo unificado e consolidado em `docs/PLAN.md` como fonte única da verdade (duplicidade com `planejamento2.md` removida) e Gate S0 aprovado. |
| **Implementação** | **em andamento** | Dev 1–4 + Implementador | `develop` | `b4852bd` | Sprint 1 100% concluída. S2-T5, S2-T6 e S2-T7 aprovadas. Próxima task: S2-T8 (Testes de Integração). |
| **Validação** | **não iniciada** | Dev 1–4 + Revisor | — | — | Reserva obrigatória de US$ 7,50 (30% dos US$ 25 da Featherless) preservada para os testes finais com modelos reais, ensaio e Demo Day. |

---

## 2. Sprints e Tasks

| Sprint / Task | Fase | Estado | Responsável (Dev + Agente) | Branch Prevista | Último Commit | Dependências / Observações |
| --- | --- | --- | --- | --- | --- | --- |
| **S0-T0** Planejamento Unificado e Gate S0 | Planejamento | **aprovada** | Dev 1 + Planejador / Revisor | `main` / `develop` | — | Sem bloqueios de arquitetura; planejamento único consolidado em `docs/PLAN.md`. |
| **S1-T1** PostgreSQL, Modelos SQL e Contratos Pydantic v2 | Implementação | **aprovada** | Dev 1 + Implementador / Revisor | `develop` (via PR #1) | `0afa816` | Postgres, modelos SQLAlchemy 2.0, schemas Pydantic v2 com run_id e seed concluídos e auditados (97.6% cobertura). |
| **S1-T2** Cliente LLM (Mock/Featherless), Custo, Guardrails, LGPD e Langfuse | Implementação | **aprovada** | Dev 3 + Implementador / Revisor | `develop` (via PR #2) | `04da421` | Cliente LLM unificado, controle de orçamento com corte preventivo, guardrails de prompt injection, mascaramento LGPD e Langfuse aprovados (46 testes, 92.48% cobertura). |
| **S1-T3** Fluxo B — Nó S (Coletor/Validador Periódico via APScheduler) | Implementação | **aprovada** | Dev 4 + Implementador / Revisor | `develop` (via commit) | `b47d291` | Job periódico APScheduler, Google Places/fixture e validação de contato integrados (237 testes unitários). |
| **S1-T4** Shell Frontend Estilo Airbnb (Imóveis, Chat Único e Sessão ADM) | Implementação | **aprovada** | Dev 2 + Implementador / Revisor | `develop` (via PR) | `34c8c58` | Casca completa em React + TypeScript + Vite estilo Airbnb (listagem, calendário, chat e sessão ADM) integrada em develop. |
| **S1-T13** Ajuste de Contratos (TicketStatus, Nó 2 → Nó 3) e Correção dos Docs | Implementação | **aprovada** | Dev 1 + Planejador / Revisor | `develop` (via PR #4) | `7ba24a9` | Alinhamento do enum TicketStatus ao PLAN e criação do protocolo ResolverStarter (Nó 2 → Nó 3). As correções da revisão (reserva de 30% no corte de orçamento, `TICKET_TRANSITIONS`, contrato endurecido) ficaram fora do merge e foram reaplicadas em `fix/s1-t13-reapply-review-fixes`. |
| **S2-T5** Roteador Barato + Nó 1 (Comercial) + Nó 2 (Validador) | Implementação | **aprovada** | Dev 1 + Implementador / Revisor | `develop` (via PR #5) | `fe163f1` | Roteador barato com regra de custo zero para chamado aberto/cleaner, Nó 1 com checagem de conflito de datas e Nó 2 com extração tipada Pydantic integrado em develop (67 testes, 93.47% cobertura). |
| **S2-T6** Fluxo C — Nó 3 (Resolvedor em LangGraph + Urgência × Agenda) | Implementação | **aprovada** | Dev 3 + Implementador / Revisor | `develop` (via PR #6) | — | Grafo de 5 passos do Nó 3 em LangGraph com PostgresSaver, interrupt/resume para ADM, agendamento determinístico Urgência × Agenda (100% cobr.), timeouts integrados no ciclo de vida, fallback Nó S enfileirado e endpoints HTTP em /api/tickets (99 testes, 92% cobertura global). |
| **S2-T7** Integração Frontend (Sessão Agente ⇄ Anfitrião + Simulador) | Implementação | **aprovada** | Dev 2 + Implementador / Revisor | `develop` (via PR #7) | `b4852bd` | Conexão UI às APIs (Chat, Orçamentos, Aprovação ADM, Simulador e Auditoria) com Design System Zelo, 102 testes backend (92.3% cobr.) e 6 testes frontend verdes. |
| **S2-T8** Testes de Integração (Caminhos Alternativos) e Suíte de Segurança | Implementação | **não iniciada** | Dev 4 + Implementador / Revisor | `feature/s2-t8-integration-security-tests` | — | Depende de S2-T5, S2-T6. Cobre timeouts, recusa de data, sem prestador e injection. |
| **S3-T9** Testes E2E com Modelos Reais (Featherless) e Recalibração de Custo | Validação | **não iniciada** | Dev 1 + Implementador / Revisor | `fix/s3-t9-real-llm-e2e` | — | Depende de S2 concluída. Ativa modelos reais pagos e atualiza `docs/COST.md`. |
| **S3-T10** Deploy do Link Testável + Seed/Reset para Avaliadores | Validação | **não iniciada** | Dev 2 + Implementador / Revisor | `feature/s3-t10-deploy-link` | — | Depende de S2 concluída. |
| **S3-T11** Roteiro, Gravação do Vídeo e Material do Pitch (Demo Day) | Validação | **não iniciada** | Dev 3 + Implementador / Revisor | `docs/s3-t11-pitch-video` | — | Depende de S2 concluída. |
| **S3-T12** Pacote Final de Submissão e Plano B (`recorded_demo`) | Validação | **não iniciada** | Dev 4 + Implementador / Revisor | `docs/s3-t12-submission-plan-b` | — | Depende de S3-T9, S3-T10, S3-T11. |

---

## 3. Decisões Confirmadas e Diretrizes Ativas

1. **Unificação do Planejamento:** `docs/PLAN.md` é a **fonte única da verdade** oficial do projeto para escopo, arquitetura, fluxos e sprints. Arquivos transitórios de planejamento foram consolidados e removidos para eliminar duplicidades.
2. **Orçamento e Estratégia Mock-First:** Os US$ 25,00 na Featherless são exclusivos para os agentes de negócio do produto (reserva obrigatória de 30% = US$ 7,50 para a S3; teto de US$ 17,50 antes disso). Durante o desenvolvimento e testes de unidade/integração, usa-se `LLM_MODE=mock`; os modelos reais entram na etapa final.
3. **Ledger de Custos e Contabilidade Preventiva:** Chamadas a `app.core.llm.generate` obrigatoriamente registram gasto no ledger (DB e acumulador em memória), garantindo que os limites preventivos de corte por run (`MAX_COST_PER_RUN_USD = US$ 0,03`) e global (`US$ 25,00`) sejam aplicados com precisão.
4. **Arquitetura de 3 Fluxos + Roteador de Chat Único:**
   - Ponto único de chat no imóvel com roteador barato (`dúvida → Nó 1` / `problema de inquilino ou camareira → Nó 2`).
   - O Roteador checa primeiro chamados abertos de manutenção no imóvel para encaminhar diretamente ao Nó 2 com custo zero (sem chamada a LLM).
   - **Fluxo A (Aquisição):** Nó 1 atende até a reserva confirmada ("temos inquilino"), checando disponibilidade de datas na agenda antes de criar o `Booking` e mantendo o contrato `ChatMessageOutput`.
   - **Fluxo B (Coleta Periódica):** Nó S roda via `APScheduler`, valida contato dos prestadores e salva apenas os confirmados no PostgreSQL.
   - **Fluxo C (Manutenção):** Nó 2 gera ticket Pydantic estruturado (`response_format`) → Nó 3 (LangGraph) pede orçamentos (sem negociar preço) → notifica o ADM na **sessão Agente ⇄ Anfitrião do imóvel** → ADM escolhe o prestador → Nó 3 propõe data conforme **urgência × agenda** → prestador confirma (se recusar, volta ao passo 3) → avisa inquilino se estiver hospedado.
5. **Stack Técnica:** Python 3.12, FastAPI, Pydantic v2, LangGraph (no Nó 3), APScheduler, PostgreSQL, React + TypeScript, Langfuse, cobertura mínima de **70% no código novo**.
6. **Desafio Tako:** Não concorre (foco 100% em imóveis de temporada).
7. **LGPD:** Telefones de prestadores e dados pessoais de hóspedes ficam apenas no PostgreSQL e são mascarados antes de logs e traces do Langfuse.

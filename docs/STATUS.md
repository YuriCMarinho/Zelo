# Status do Projeto — Fonte da Verdade (`STATUS.md`)

Atualizado em: `2026-11-08` (alinhado a `docs/PLAN.md` como fonte única da verdade).

Estados permitidos: **não iniciada** | **em andamento** | **em revisão** | **aprovada** | **bloqueada**.
**Versão canônica: a de `develop`.** As cópias em `main` e nas branches de task podem estar defasadas; leia sempre `git show origin/develop:docs/STATUS.md`.
Todo agente deve ler este arquivo antes de iniciar qualquer ação e atualizá-lo ao iniciar e ao concluir seu trabalho.

---

## 1. Visão por Fase

| Fase | Estado | Responsável | Branch Atual | Último Commit | Bloqueios / Decisões Confirmadas |
| --- | --- | --- | --- | --- | --- |
| **Planejamento** | **aprovada** | Orquestrador → Planejador / Revisor | `main` / `develop` | — | Escopo unificado e consolidado em `docs/PLAN.md` como fonte única da verdade (duplicidade com `planejamento2.md` removida) e Gate S0 aprovado. |
| **Implementação** | **aprovada** | Dev 1–4 + Implementador | `develop` | `f9af095` | Sprint 1 e Sprint 2 100% concluídas. S2-T5, S2-T6, S2-T7 e S2-T8 aprovadas. Próxima etapa: Sprint 3 (Validação com Modelos Reais e Deploy). |
| **Validação** | **em andamento** | Dev 1–4 + Revisor | `fix/s3-t9-real-llm-e2e` | — | Reserva obrigatória de US$ 7,50 (30% dos US$ 25 da Featherless) liberada sob controle exclusivo para S3-T9 e Demo Day. |

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
| **S2-T14** Fluxo Real do Prestador no Nó 3 (espera, timeouts, fallback e aviso) | Implementação | **aprovada** | Dev 3 + Implementador / Revisor | `feature/s2-t14-provider-real-flow` | `db5ff69` | Fluxo do prestador acessível na sessão ADM, respostas pelos endpoints, aprovação sem sucesso fictício, atualização automática e retomada segura após coleta. Validado com 196 testes backend (92,01% cobertura) e 56 testes frontend; detalhes na seção 4. |
| **S2-T8** Testes de Integração (Caminhos Alternativos) e Suíte de Segurança | Implementação | **aprovada** | Dev 4 + Implementador / Revisor | `develop` (via PR #8) | `f9af095` | Suíte completa com 162 testes verdes (92.5% cobertura), cobrindo caminho feliz, 5 caminhos alternativos, 100% prompt injection bloqueado e LGPD verificado. |
| **S3-T9** Testes E2E com Modelos Reais (Featherless) e Recalibração de Custo | Validação | **aprovada** | Dev 1 + Implementador / Revisor | `develop` (via PR #10) | `6cc7440` | Bateria E2E sob marcador @pytest.mark.real_llm, telemetria Langfuse e Seção 9 de calibração empírica no COST.md concluídas e integradas em develop (165 testes verdes, 92.5% cobr.). |
| **S3-T10** Deploy do Link Testável + Seed/Reset para Avaliadores | Validação | **aprovada** | Dev 2 + Implementador / Revisor | `develop` (via PR #12) | `ce22307` | Container Docker unificado multi-stage testado (FastAPI + React SPA), endpoint POST /api/demo/reset funcional, botão e modal no frontend e docs/DEPLOY.md concluídos (166 testes backend, 11 testes frontend). |
| **S3-T11** Roteiro, Gravação do Vídeo e Material do Pitch (Demo Day) | Validação | **não iniciada** | Dev 3 + Implementador / Revisor | `docs/s3-t11-pitch-video` | — | Depende de S2 concluída. |
| **S3-T12** Pacote Final de Submissão e Plano B (`recorded_demo`) | Validação | **em revisão** | Dev 4 + Implementador / Revisor | `docs/s3-t12-submission-plan-b` | `606be0e` | Plano B implementado e validado; pacote e inventário preparados. Não atende ainda ao aceite final dos 5 entregáveis: faltam vídeo/pitch da S3-T11, deploy acessível e confirmação de acesso da banca ao repositório. Ver seção 5. |
| **S4-T15** Governança de Reservas do Anfitrião, Isolamento de Canais e Chat Multi-Turn | Implementação / Validação | **aprovada** | Dev 1–2 + Implementador / Revisor | `develop` | `52c5dad` | Reserva em 2 etapas (`pending_approval` → aceite/recusa do anfitrião pelo valor `R$ X` ou motivo), isolamento de canais (`guest` vs `cleaner`) e `session_id` por navegador, agilidade de resposta do chat (0,5s–1,1s) e memória multi-turn. Validado com 215 testes backend + 58 testes frontend. |

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

---

## 4. Revisão da S2-T14 — 2026-11-08

**Veredito: aprovada na revisão do commit `db5ff69`, na branch `feature/s2-t14-provider-real-flow`.** Os oito critérios de aceite da S2-T14 foram atendidos na implementação, incluindo a correção da coleta rápida do Nó S e as três correções da interface. A publicação do código não representa validação de um deploy remoto.

| Critério do `PLAN.md` | Resultado |
| --- | --- |
| 1. Valores de orçamento vêm da resposta do prestador | Atendido no backend: pedidos começam com `amount=null`; preço e resposta são registrados pelo endpoint do prestador. |
| 2. Confirmação/recusa de data e escalonamento após 3 recusas | Atendido no backend e coberto pelos testes do resolvedor. |
| 3. Timeouts pelo APScheduler retomam o grafo | Implementado; callback assíncrono também verificado com um APScheduler real. Os jobs atuais são mantidos em memória e não são recuperados após reinício do processo. |
| 4. Coleta assíncrona e retomada quando surge prestador | Corrigido: a coleta começa após a persistência da pausa do grafo, evitando perder `providers_ready`. Teste de regressão adicionado. |
| 5. `tenant_notified` somente quando houver hóspede | Atendido no backend, com testes para imóvel ocupado e vazio. A exibição persistente desse aviso no chat é uma integração adicional da S2-T7. |
| 6. Guardrail para texto do prestador | Implementado nos endpoints de orçamento e devolutiva de data; bloqueio de injection coberto nos testes. |
| 7. Transições de estado validadas | Implementado com `_set_status` e `is_valid_ticket_transition`. |
| 8. Simulador da UI responde como prestador | Implementado no painel “Ações do prestador (demonstração)” da sessão Agente ⇄ Anfitrião; envia orçamentos e aceita/recusa datas pelos endpoints reais. |

Correções da revisão incluídas no commit `db5ff69`:

1. `ProviderSimulator` está acessível na sessão Agente ⇄ Anfitrião, com apenas ações de prestador no painel de demonstração. Envio de orçamento e aceite/recusa usam os endpoints do chamado; aprovação continua separada, como ação do anfitrião. Três recusas exibem o escalonamento real ao anfitrião.
2. `approveQuote` e `startTicketResolution` propagam erros de rede, HTTP e respostas inválidas sem fabricar sucesso. Foram removidos os chamados/orçamentos fictícios de `PropertyWorkspace` e o aviso de agendamento fabricado pela aprovação.
3. `PropertyWorkspace` consulta chamado e orçamentos a cada 5 segundos, ao voltar à janela, trocar de aba e após ações locais. A data exibida vem do chamado confirmado; requisições antigas não atualizam componentes desmontados e os timers são cancelados na saída.

Validação atual: **56 testes do frontend aprovados**, incluindo o ciclo orçamento → aprovação → recusa/aceite → visita confirmada, falhas HTTP/rede e atualização externa com limpeza dos timers; build, TypeScript e lint aprovados. Última suíte completa do backend: **196 testes aprovados, 4 testes pagos pulados e 92,01% de cobertura**; teste adicional de disparo real do APScheduler aprovado. Recuperação de timers após reinício e integração persistente dos avisos ao chat continuam fora destas três correções.


## 5. Entrega da S3-T12 — 2026-11-08

Implementado o modo `recorded_demo` com oito respostas reais capturadas de Qwen/Featherless, latência assíncrona configurável e nenhuma chamada externa de inferência, busca de prestadores ou telemetria durante a reprodução. Cenários sem gravação e modos inválidos falham sem recorrer à API paga. O registro de custos da reprodução é zero, com sinalização `is_mock=true`.

O pacote inclui `SUBMISSION.md`, `TOOLS.md`, `submission.json`, `RECORDED_DEMO.md` e um validador de arquivos/links. README e guia de deploy apontam para os materiais e distinguem funcionalidades reais, simuladas e pendentes.

Validação: **211 testes backend aprovados, 4 testes pagos pulados e 92,07% de cobertura**; **56 testes frontend aprovados**, build, tipos e lint aprovados. Smoke com processo independente e banco temporário: boot em **2,995 s**, ciclo HTTP completo em **3,787 s**, dois orçamentos, recusa/aceite de data, evento `tenant_notified` e custo zero. Esses tempos são locais e não garantem cold start em hospedagem gratuita; as pausas intencionais do chat não entram nessa medição de ativação.

**Pendências para aprovar a task e enviar o formulário:** vídeo e material de pitch da S3-T11 ainda não fornecidos; URL documentada do app e seu `/health` retornam 404; repositório retorna 404 no acesso anônimo. O Git autenticado local funciona. O validador `python3 scripts/check_submission.py --check-links` retorna `ready=false` com essas pendências. Não foram inventados links nem declarada uma submissão concluída.

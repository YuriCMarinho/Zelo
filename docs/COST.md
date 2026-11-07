# Estimativa e Controle de Custo (`COST.md`)

Atualizado em: `2026-11-07` (alinhado a `docs/PLAN.md`).

---

## Premissas e Regras Orçamentárias

- **Orçamento de inferência do produto (Featherless):** **US$ 25,00** em créditos, exclusivos para os agentes de negócio que rodam no sistema. Os 3 agentes de desenvolvimento (Planejador, Implementador e Revisor) rodam fora da Featherless (IDE/CLI) e **não** consomem este saldo.
- **Reserva obrigatória de 30%:** **US$ 7,50** bloqueados exclusivamente para testes finais E2E, ensaio e Demo Day (Sprint 3). O teto máximo acumulado antes da reserva é de **US$ 17,50**.
- **Estratégia de execução (Mock-First):** Durante o desenvolvimento e nos testes automatizados de unidade e integração (Sprints 1 e 2), **todas as chamadas usam LLM mockado e simulações por padrão (custo US$ 0,00)**. Os modelos reais pagos na Featherless são acionados apenas na reta final (bateria de validação de modelos, testes E2E marcados com `@pytest.mark.real_llm`, ensaio e Demo Day).
- **Preços de referência da Featherless (por 1M de tokens):**
  - [`Qwen/Qwen3.5-4B`](https://featherless.ai/models/Qwen/Qwen3.5-4B): **US$ 0,10 entrada / US$ 0,20 saída**
  - [`Qwen/Qwen3.5-9B`](https://featherless.ai/models/Qwen/Qwen3.5-9B): **US$ 0,17 entrada / US$ 0,25 saída**
  - [`Qwen/Qwen3.5-27B`](https://featherless.ai/docs/request-pricing-and-credits) (apenas fallback): **US$ 0,30 entrada / US$ 2,40 saída**
  - *Nota sobre modalidade de cobrança:* Caso a chave da Featherless opere sob plano de capacidade fixa (concorrência em vez de desconto por token), o ledger interno do sistema continuará calculando o custo equivalente em dólares por token **e** aplicará semáforo de limite de concorrência (`MAX_CONCURRENT_LLM_REQUESTS`, ex.: 2 a 4 chamadas simultâneas) e rate limit por minuto.

---

## 1. Custo por Execução de Fluxo (Modelos Reais)

Fórmula por chamada: `(tokens_entrada × preço_entrada + tokens_saída × preço_saída) / 1.000.000`.
Toda chamada define `model` e `max_tokens` explicitamente.

### 1.1 Roteador de Entrada (Ponto Único de Chat do Imóvel)
Classifica se a mensagem recebida no imóvel é **dúvida comercial/reserva (→ Nó 1)** ou **relato de problema de inquilino/camareira (→ Nó 2)**. Regras determinísticas (palavras-chave óbvias ou sessão já vinculada a ticket ativo) resolvem sem LLM quando possível.

| Etapa / Chamada | Agente / Modelo | Tokens Entrada (est.) | Tokens Saída (est. / `max_tokens`) | US$/1M (In / Out) | Custo Estimado (US$) |
| --- | --- | ---: | ---: | ---: | ---: |
| Guardrail de entrada (sanitização + injection check) | Guardrail (`Qwen3.5-4B`) | 250 | 40 / 64 | 0,10 / 0,20 | 0,000033 |
| Classificação de intenção (dúvida vs. problema) | Roteador (`Qwen3.5-4B`) | 300 | 30 / 48 | 0,10 / 0,20 | 0,000036 |
| **Subtotal Roteador (por mensagem inicial)** | | **550** | **70** | | **0,000069** |

### 1.2 Fluxo A — Aquisição / Atendimento Comercial (Nó 1)
Conversa calorosa com potencial hóspede para tirar dúvidas sobre o imóvel até a confirmação da reserva ("temos inquilino"). Estimativa para uma conversa média de **3 turnos**.

| Etapa / Chamada | Agente / Modelo | Tokens Entrada (acum. 3 turnos) | Tokens Saída (acum. / `max_tokens` por turno) | US$/1M (In / Out) | Custo Estimado (US$) |
| --- | --- | ---: | ---: | ---: | ---: |
| Roteador inicial + Guardrails (3 mensagens do cliente) | Roteador + Guardrail (`Qwen3.5-4B`) | 800 | 120 / 64 | 0,10 / 0,20 | 0,000104 |
| Respostas calorosas e fechamento da reserva (3 turnos) | Nó 1 Comercial (`Qwen3.5-9B`) | 2.400 | 540 / 256 | 0,17 / 0,25 | 0,000543 |
| **Subtotal Fluxo A completo (3 turnos)** | | **3.200** | **660** | | **0,000647** |

### 1.3 Fluxo B — Coleta e Validação de Prestadores (Nó S — Job Periódico APScheduler)
Job assíncrono com `run_id` próprio que busca prestadores por categoria/região, envia mensagem de validação de contato e interpreta a resposta para gravar no PostgreSQL apenas prestadores confirmados (lote de 5 novos candidatos por execução).

| Etapa / Chamada | Agente / Modelo | Tokens Entrada (lote de 5) | Tokens Saída (lote / `max_tokens` cada) | US$/1M (In / Out) | Custo Estimado (US$) |
| --- | --- | ---: | ---: | ---: | ---: |
| Extração de candidatos (Google Places API / Fixture) | Tool externa (sem LLM) | 0 | 0 | 0 / 0 | 0,000000 |
| Guardrail nas 5 respostas de confirmação de contato | Guardrail (`Qwen3.5-4B`) | 1.000 | 150 / 48 | 0,10 / 0,20 | 0,000130 |
| Extração de confirmação/disponibilidade (5 respostas) | Nó S Validador (`Qwen3.5-4B`) | 1.250 | 200 / 64 | 0,10 / 0,20 | 0,000165 |
| **Subtotal Fluxo B por job (5 prestadores)** | | **2.250** | **350** | | **0,000295** |

### 1.4 Fluxo C — Manutenção Ponta a Ponta (Nó 2 → Nó 3 ⇄ ADM → Prestador → Inquilino)
Carrega o mesmo `run_id` por ticket. Inclui relato de inquilino/camareira (com 1 pergunta de esclarecimento), orçamento com 3 prestadores do DB, notificação ao ADM na sessão do imóvel, proposta de data conforme **urgência × agenda**, confirmação do dia pelo prestador e aviso ao inquilino hospedado.

| Etapa / Chamada | Agente / Modelo | Tokens Entrada (est.) | Tokens Saída (est. / `max_tokens`) | US$/1M (In / Out) | Custo Estimado (US$) |
| --- | --- | ---: | ---: | ---: | ---: |
| 0. Roteamento inicial (problema → Nó 2) | Roteador + Guardrail (`Qwen3.5-4B`) | 550 | 70 / 64 | 0,10 / 0,20 | 0,000069 |
| 1. Nó 2: Esclarecimento + Classificação do ticket (Pydantic) | Nó 2 Validador (`Qwen3.5-4B`) | 1.400 | 280 / 256 | 0,10 / 0,20 | 0,000196 |
| 2. Nó 3 (Passo 1): Redação do pedido de orçamento (template + contexto) | Nó 3 Resolvedor (`Qwen3.5-4B`) | 600 | 140 / 192 | 0,10 / 0,20 | 0,000088 |
| 3. Nó 3 (Passo 1): Guardrail + parsing de 3 orçamentos recebidos | Guardrail + Nó 3 (`Qwen3.5-4B`) | 1.800 | 300 / 128 cada | 0,10 / 0,20 | 0,000240 |
| 4. Nó 3 (Passo 2): Síntese comparativa para a sessão Agente ⇄ ADM | Nó 3 Resolvedor (`Qwen3.5-9B`) | 1.400 | 260 / 320 | 0,17 / 0,25 | 0,000303 |
| 5. Nó 3 (Passo 3): Proposta de datas ao prestador escolhido (urgência × agenda) | Nó 3 Resolvedor (`Qwen3.5-4B`) | 550 | 120 / 160 | 0,10 / 0,20 | 0,000079 |
| 6. Nó 3 (Passo 4): Guardrail + interpretação da "devolutiva do dia" do prestador | Guardrail + Nó 3 (`Qwen3.5-4B`) | 650 | 100 / 128 | 0,10 / 0,20 | 0,000085 |
| 7. Nó 3 (Passo 5): Aviso ao inquilino sobre o dia da manutenção | Nó 3 Resolvedor (`Qwen3.5-4B`) | 450 | 110 / 160 | 0,10 / 0,20 | 0,000067 |
| **Subtotal Fluxo C completo (por ticket)** | | **7.400** | **1.380** | | **0,001127** |

---

## 2. Custos Fora da Featherless (Não-LLM)

Todos os recursos externos operam em camada gratuita ou simulada no MVP, com teto explícito:

| Recurso Externo | Uso no Produto | Estratégia no Hackathon / MVP | Orçamento Alocado | Limite de Segurança |
| --- | --- | --- | ---: | --- |
| **Google Places API** | Extração periódica de prestadores por categoria/região no Nó S | DB já inicia pré-populado para o MVP; chamadas reais à Places API usam crédito gratuito do Google Cloud (Text Search / Nearby Search) apenas em jobs controlados | **US$ 0,00** (Free Tier) | Máx. 50 chamadas no hackathon (`MAX_PLACES_CALLS=50`), com cache em banco |
| **Canal de Mensagens (Hóspede, Camareira, Prestador, ADM)** | Chat estilo Airbnb no imóvel + sessão exclusiva Agente ⇄ Anfitrião (ADM) + simulador de prestadores | Simulado integralmente na interface web do sistema (PostgreSQL + WebSockets/polling). Sem cobrança por mensagem | **US$ 0,00** | Allowlist obrigatória caso algum webhook externo de teste seja habilitado |
| **Hospedagem e Banco de Dados (PostgreSQL)** | Link testável da submissão + persistência de tickets, prestadores, agenda e checkpoints LangGraph | Docker Compose em desenvolvimento; deploy em camada gratuita (Render / Railway / Fly.io + Neon / Supabase Free Tier) | **US$ 0,00** (Free Tier) | Monitorar conexões e armazenamento do plano gratuito |

---

## 3. Cenários por Execução Completa (Fluxos A + B + C)

Soma base de uma rodada completa (1 Fluxo A + 1 job Fluxo B + 1 ticket Fluxo C) = **US$ 0,002069**.

| Cenário | Premissas consideraras | Custo Fluxo C (Manutenção) | Custo Rodada Completa (A+B+C) |
| --- | --- | ---: | ---: |
| **Otimista** | Sem retries, 1 turno de esclarecimento no Nó 2, prestador aceita a 1ª data proposta | US$ 0,001127 | **US$ 0,002069** |
| **Esperado** | +20% de tokens por conversa mais longa, 1 lembrete de timeout e 1 retry médio de schema | US$ 0,001352 | **US$ 0,002483** |
| **Pessimista** | Conversas 2× mais longas, tentativa de prompt injection, prestador recusa a 1ª data (volta ao passo 3 do Nó 3), retries máximos e acionamento de fallback `9B`/`27B` | US$ 0,005600 | **US$ 0,009500** |

---

## 4. Projeção Total por Fase e Reserva de 30%

Como o desenvolvimento inicial e os testes automatizados padrão usam **mocks e simulações**, o consumo real de créditos concentra-se na validação final dos modelos, nos testes E2E reais, no ensaio e no Demo Day.

| Fase | Execuções Reais Estimadas | Cenário Baseado | Custo Estimado (US$) | Teto Alocado (Envelope US$) |
| --- | --- | --- | ---: | ---: |
| **S0–S1 (Setup, Contratos, Guardrails e Coletor)** | 10 chamadas de smoke test (restante 100% mockado) | Esperado | US$ 0,02 | US$ 2,50 |
| **S2 (Implementação dos Fluxos A, B e C)** | 40 execuções reais de calibração de prompt (testes de integração usam mock) | Esperado / Pessimista | US$ 0,25 | US$ 7,50 |
| **Testes Automatizados Marcados (`real_llm`) ao fim da S2** | 60 execuções completas (incluindo bateria de 20 exemplos por tarefa) | Pessimista | US$ 0,60 | US$ 7,50 |
| **Subtotal Desenvolvimento + Validação Prévia (Teto 70%)** | **110 execuções reais** | | **US$ 0,87** | **US$ 17,50 (Máx.)** |
| **S3 — Testes E2E Finais e Ensaio do Pitch** | 40 execuções completas | Pessimista | US$ 0,40 | Parte da reserva de US$ 7,50 |
| **S3 — Demo Day + Avaliadores no Link Testável** | 100 execuções completas | Pessimista | US$ 0,95 | Parte da reserva de US$ 7,50 |
| **Subtotal Reserva Obrigatória (30%)** | **140 execuções reais** | | **US$ 1,35** | **US$ 7,50 (Bloqueado até S3)** |
| **TOTAL GERAL PROJETADO** | **250 execuções reais** | | **US$ 2,22** | **US$ 25,00** |

> Mesmo com margem ampla de segurança, o gasto estimado em LLM é de ~US$ 2,22 frente aos US$ 25,00 disponíveis, pois o time adotou a diretriz de **desenvolver com mocks/simulações e ativar modelos reais na etapa final**. Ainda assim, os tetos de código impedem qualquer loop acidental de drenar o orçamento.

---

## 5. Escolha de Modelo por Tarefa

Critério de qualidade: validar com exemplos em português garantindo ≥95% de aderência ao schema Pydantic v2, zero contratações sem aprovação do ADM e bloqueio de 100% da suíte de prompt injection.

| Tarefa / Nó | Modelo Principal (Mais Barato) | Modelo Fallback | Justificativa e Regra de Uso |
| --- | --- | --- | --- |
| **Guardrail de Entrada** (hóspede, camareira, prestador) | `Qwen/Qwen3.5-4B` | `Qwen/Qwen3.5-9B` | Precedido por filtro regex/tamanho determinístico; saída booleana + motivo curto (`max_tokens=64`). |
| **Roteador do Chat Único** (dúvida → Nó 1; problema → Nó 2) | `Qwen/Qwen3.5-4B` | `Qwen/Qwen3.5-9B` | Classificação binária rápida (`max_tokens=48`); usa regra sem LLM se já houver ticket aberto na sessão. |
| **Nó 1 — Comercial (Chatbot)** | `Qwen/Qwen3.5-9B` | `Qwen/Qwen3.5-27B` | Exige tom caloroso e persuasivo em português para converter a reserva (`max_tokens=256`). |
| **Nó 2 — Validador (Classificação de Ticket)** | `Qwen/Qwen3.5-4B` | `Qwen/Qwen3.5-9B` | Extração estruturada (categoria, urgência, local) com schema Pydantic v2 (`max_tokens=256`). |
| **Nó S — Validador de Contato de Prestador** | `Qwen/Qwen3.5-4B` | `Qwen/Qwen3.5-9B` | Interpreta se o prestador confirmou atuação e contato válido (`max_tokens=64`). |
| **Nó 3 — Extração de Orçamento e Confirmação de Dia** | `Qwen/Qwen3.5-4B` | `Qwen/Qwen3.5-9B` | Extrai valor/observação do prestador e interpreta aceitação/recusa da data (`max_tokens=128`). |
| **Nó 3 — Síntese de Orçamentos para o ADM** | `Qwen/Qwen3.5-9B` | `Qwen/Qwen3.5-27B` | Compara propostas recebidas e apresenta resumo claro na sessão Agente ⇄ Anfitrião (`max_tokens=320`). |
| **Nó 3 — Mensagem de Data e Aviso ao Inquilino** | `Qwen/Qwen3.5-4B` | `Qwen/Qwen3.5-9B` | A regra `urgência × agenda` é 100% determinística em Python; o LLM apenas redige a mensagem cordial (`max_tokens=160`). |

---

## 6. Alavancas de Economia

1. **Mock por padrão (`LLM_MODE=mock`):** Desenvolvimento local, CI e testes de unidade/integração usam provedor mockado determinístico com custo zero; `LLM_MODE=featherless` só é ligado nos testes finais marcados e na demo.
2. **Regras determinísticas antes do LLM:** Tamanho máximo de mensagem (ex.: 1.500 caracteres), bloqueio regex de padrões óbvios de injection, cálculo de datas livres na agenda (`urgente` vs. `não urgente`) e verificação de timeout são feitos em Python puro sem gastar tokens.
3. **`max_tokens` estrito em toda chamada:** Nenhuma chamada ao cliente Featherless é permitida sem `max_tokens` explícito (validado pelo wrapper de LLM e auditado pelo Revisor).
4. **Janela deslizante e resumo de histórico:** Conversas nos Nós 1 e 2 enviam apenas as últimas 6 mensagens + resumo estruturado do estado atual.
5. **Cache de respostas e dados estáticos:** Dados do imóvel, FAQ comercial básico e resultados da Google Places API ficam cacheados no PostgreSQL.
6. **Retry máximo = 1:** Apenas para erro transitório HTTP (5xx/429) ou falha de parsing Pydantic, sempre dentro do teto do `run_id`.

---

## 7. Tetos, Alertas e Configuração no Langfuse

- **Tetos configuráveis via variáveis de ambiente (com corte automático antes da chamada):**
  - Teto por execução (`MAX_COST_PER_RUN_USD`): **US$ 0,03** por `run_id`
  - Tetos por Sprint: **S0 = US$ 0,50**, **S1 = US$ 2,00**, **S2 = US$ 15,00** (soma pré-reserva ≤ US$ 17,50), **S3 = US$ 7,50** (reserva exclusiva)
  - Teto global (`MAX_COST_GLOBAL_USD`): **US$ 25,00**
- **Alertas automáticos (log estruturado + badge no painel do ADM):**
  - **50%** do orçamento (US$ 12,50 global ou 50% da sprint atual)
  - **75%** do orçamento (US$ 18,75 global ou 75% da sprint atual)
  - **90%** do orçamento (US$ 22,50 global ou 90% da sprint atual)
  - **100%:** bloqueio imediato (`BudgetExceededError`) com fallback gracioso no painel.
- **Preços da Featherless no Langfuse (obrigatório):**
  - Como os modelos da Featherless não possuem tabela nativa de preços no Langfuse, o sistema deve:
    1. Cadastrar as *Model Definitions* no projeto Langfuse (`Qwen/Qwen3.5-4B`, `Qwen/Qwen3.5-9B`, `Qwen/Qwen3.5-27B`) com os preços por token de entrada e saída; **e**
    2. Enviar explicitamente o `usage` (`input`, `output`, `total`) e o `cost_details` (`input_cost`, `output_cost`, `total_cost` calculados pelo ledger do backend) em cada span/geração do SDK do Langfuse, associados ao `run_id` (`trace_id` / `session_id`).

---

## 8. Recalibração por Sprint

Ao término de cada sprint, o **Revisor/Auditor** compara o custo acumulado no Langfuse e no ledger PostgreSQL contra a estimativa deste documento:
- Se o desvio absoluto entre o custo real por execução e o estimado ultrapassar **±25%**, o **Planejador** deve atualizar o `docs/COST.md`, registrar a causa (ex.: tamanho de prompt, retries, uso de fallback) e ajustar os limites antes de o Revisor liberar o gate da sprint seguinte.

# PROMPT_ORQUESTRADOR v2

# PAPEL

Você é o orquestrador de um time de **3 agentes de IA de desenvolvimento** (Planejador, Implementador e Revisor/Auditor) que apoia 4 desenvolvedores humanos em um hackathon. Sua tarefa agora é gerar os arquivos de instrução dos agentes e o plano de implementação inicial. **NÃO escreva código de aplicação nesta etapa.**

---

# CONTEXTO DO PROJETO

Hackathon: construir um fluxo de agentes de IA de ponta a ponta que resolva um problema real.

- **Prazo total:** 24h a 30h até o Demo Day (dividido em 4 sprints curtas: S0 a S3).

- **Orçamento de inferência do produto:** US$ 25 em créditos Featherless, compartilhados pelos 4 devs para os agentes do sistema (produto). **Reserva obrigatória de 30% (US$ 7,50)** para testes finais, ensaio e Demo Day; o desenvolvimento usa no máximo US$ 17,50.

  - **Agentes de desenvolvimento vs. Produto:** Os 3 agentes de desenvolvimento (Planejador/Implementador/Revisor) rodam fora da Featherless (IDE/CLI). Os US$ 25 da Featherless são exclusivos para os agentes de negócio do sistema.

  - **Estratégia de consumo e cobrança:** Inicialmente, durante o desenvolvimento e testes de integração, usam-se **apenas dados mockados e simulações** (custo zero de LLM). Na etapa final, iniciam-se os testes e validações com os modelos reais pagos na Featherless (controlando tokens/créditos e limites de concorrência/rate limit em `docs/COST.md`).

- **Custos fora da Featherless:** Google Places API, canal de mensagens e hospedagem do link testável + banco de dados. Devem constar no `docs/COST.md` com orçamento próprio, mesmo que seja zero (camada gratuita/simulação).

- **Desafio opcional do hackathon:** **Não** concorre ao Desafio Tako (foco 100% em gestão de imóveis de temporada, não RH).

**Produto:** plataforma para gestores de imóveis de temporada (simulando uma experiência simples estilo Airbnb) que atende hóspedes/inquilinos de forma calorosa e resolve problemas de manutenção do imóvel de ponta a ponta, encontrando, orçando e agendando prestadores (encanador, eletricista, pintor, organizador, manutenção geral), com o gestor (ADM/anfitrião) decidindo a contratação dentro de uma sessão dedicada de comunicação Agente ⇄ Anfitrião na página daquele imóvel específico.

**Autonomia dos agentes:** Os agentes apenas coletam orçamentos, organizam opções e sugerem; **o ADM (anfitrião) sempre aprova e escolhe o prestador** antes de qualquer contratação ou agendamento.

**Canal de mensagens com hóspedes, camareiras e prestadores:** Simulação web integrada ao próprio sistema (estilo Airbnb), com chat unificado para hóspede/camareira, simulação de mensagens com prestadores (ou allowlist de contatos dos devs) e uma sessão exclusiva dentro de cada imóvel para a comunicação entre o agente e o anfitrião (ADM).

**Fonte da agenda do imóvel:** Tabela mockada/persistida no banco de dados PostgreSQL por imóvel (`property_id`).

**Critérios de avaliação do hackathon (pesos iguais):** protótipo e aderência, viabilidade como startup, pitch, criatividade. A submissão exige descrição, vídeo, link testável, material do Demo Day e lista de ferramentas. O plano deve garantir que cada um desses itens tenha dono e prazo.

---

# FLUXO DO PRODUTO (agentes de negócio)

Referência visual: diagrama Excalidraw do time. Não confundir estes agentes de negócio com os 3 agentes de desenvolvimento (Planejador, Implementador, Revisor).

O produto tem **três fluxos independentes**, ligados apenas pelo DB e pelo `property_id`, com um **ponto único de chat com roteador barato** na entrada do imóvel:

- **Roteador de Entrada (chat único do imóvel):** recebe a mensagem e classifica de forma barata (regra determinística + modelo pequeno) se é dúvida comercial/pré-reserva (encaminha ao **Nó 1**) ou relato de problema/manutenção vindo de inquilino ou camareira (encaminha ao **Nó 2**).

- **Fluxo A, aquisição:** Nó X (opcional, fora do MVP) → Roteador → Nó 1 → reserva confirmada ("temos inquilino").

- **Fluxo B, coleta de prestadores (assíncrono, agendado):** Nó S → DB de prestadores validados.

- **Fluxo C, manutenção:** problema relatado (inquilino/camareira) → Roteador → Nó 2 → Nó 3 ⇄ ADM (sessão Agente ⇄ Anfitrião no imóvel) → Nó 3 ⇄ prestador → aviso ao inquilino.

| Nó | Agente | Responsabilidade |
| --- | --- | --- |
| R | **Roteador de Entrada** | Ponto único de chat: encaminha dúvidas sobre o imóvel/reserva ao Nó 1 e relatos de manutenção (de inquilino ou camareira) ao Nó 2. |
| X | **Marketing** (opcional) | Cria o anúncio do imóvel: preço e descrição. Fora do MVP. |
| 1 | **Comercial (chatbot)** | Conversa de forma calorosa com o potencial cliente e tira dúvidas sobre o imóvel até a reserva. Seu papel termina quando há inquilino. |
| 2 | **Validador (chatbot)** | Recebe o problema relatado pelo **inquilino ou pela camareira**, faz perguntas de esclarecimento se necessário, **classifica** (categoria: encanador, eletricista etc.; urgência; local no imóvel) e gera um ticket estruturado (schema Pydantic). Aciona o Nó 3. |
| S | **Scraper/Validador de prestadores** | Job **periódico** (não acionado por ticket) que extrai prestadores por categoria/região do Google Maps (Google Places API), envia mensagem para validar o contato, recebe a confirmação e **grava no DB apenas prestadores que confirmaram**. |
| 3 | **Resolvedor** | Consome o DB de prestadores, pede orçamentos, notifica o ADM na sessão do imóvel, marca o dia com o prestador escolhido, recebe a confirmação do dia e, se houver hóspede no imóvel, avisa o inquilino. |
| ADM | **Gestor / Anfitrião (humano)** | Na sessão de comunicação com o agente dentro do imóvel, recebe a notificação com os orçamentos, seleciona o prestador de melhor valor e devolve a escolha ao Nó 3. |

**Sequência do Nó 3** (renumerada; o diagrama pula o passo 3 e repete o 4):

1. Pede orçamento a N prestadores da categoria/região (do DB); recebe os orçamentos de volta (com timeout).

2. Notifica o ADM (na sessão Agente ⇄ Anfitrião do imóvel) com os orçamentos recebidos; o ADM devolve o prestador escolhido.

3. Consulta a agenda do imóvel e propõe datas ao prestador escolhido conforme a urgência (ver decisões).

4. Prestador devolve a confirmação do dia ("devolutiva do dia"); se recusar, volta ao passo 3.

5. Se o inquilino estiver hospedado na data, avisa o inquilino do dia da manutenção. Registra o resultado e fecha o ticket.

**Decisões assumidas (confirmadas com o time):**

- **Problema não passa pelo Nó 1.** O Nó 1 termina na reserva; na entrada, um **ponto único de chat com roteador barato** (regra ou modelo pequeno) manda dúvida → Nó 1 e problema → Nó 2.

- **Nó S é assíncrono e agendado**, separado do Nó 3: o Nó 3 nunca faz scraping durante a negociação. Fallback: se o DB não tiver prestadores para a categoria/região do ticket, o Nó 3 dispara uma coleta sob demanda do Nó S ou avisa o ADM.

- **Data de manutenção depende da urgência:** urgente (vazamento, falta de luz) é agendada o quanto antes, mesmo com hóspede, e o hóspede é avisado; não urgente prefere dias sem hóspede.

- **O Nó 3 não negocia preço**, apenas pede orçamentos e combina a data; o ADM decide o prestador (humano no loop) e o agente nunca contrata sozinho.

- **Espera longa e estado:** o Nó 3 espera respostas de prestadores e do ADM por minutos ou horas. O estado do ticket fica persistido e cada espera tem timeout e lembrete. Este é o principal uso justificado de LangGraph (checkpointer + interrupt para o humano no loop).

- **MVP:** Fluxo C completo (Roteador → 2 → 3 ⇄ ADM → prestador → inquilino) com o DB do Nó S pré-populado; Nó S real e Nó 1 entram por prioridade de tempo. Nó X fora do MVP.

- Para a demo e os testes, o contato com prestadores e hóspedes usa interface simulada estilo Airbnb e/ou números dos próprios devs (allowlist); nenhuma mensagem real a terceiros sem aprovação explícita.

- Preferir API oficial (Google Places API) ao scraping de HTML do Maps, e registrar a decisão no plano por causa de termos de uso e estabilidade.

- Respostas de prestadores e mensagens de hóspedes/camareiras são **entrada não confiável**: passam pelos guardrails de prompt injection antes de chegar ao LLM.

- Cada passagem entre nós do Fluxo C carrega o mesmo `run_id` (por ticket) para a auditoria ponta a ponta; o Nó S tem `run_id` próprio por execução do job.

- **Dados pessoais (LGPD):** telefones de prestadores e dados de hóspedes ficam só no DB, não vão para logs nem traces sem mascaramento.

---

# STACK

- **Backend:** Python 3.12, Pydantic v2 (todos os contratos de entrada/saída dos agentes tipados), FastAPI. LangGraph apenas onde houver estado/ramificação real (justificar cada uso; caso contrário, chamadas diretas ao LLM).

- **LLM:** Featherless (API compatível com OpenAI). Modelo escolhido por tarefa, priorizando o mais barato que atenda ao critério de qualidade. Mockado por padrão durante o desenvolvimento e ativado com modelos reais na etapa final de testes/demo.

- **Observabilidade:** Langfuse (traces, spans por agente/ferramenta, custo e tokens por execução). Como os modelos da Featherless não têm preço cadastrado no Langfuse, cadastrar os preços dos modelos usados (model definitions) ou enviar o custo calculado em cada geração.

- **Agendamento do Nó S:** APScheduler (jobs periódicos em background para coleta/validação de prestadores e verificação de timeouts/lembretes).

- **Frontend:** React + TypeScript (simulando plataforma estilo Airbnb por imóvel, com chat de hóspede/camareira, sessão exclusiva Agente ⇄ Anfitrião/ADM com tickets/orçamentos/aprovação, simulação de prestadores, controle de gasto e auditoria).

- **Persistência:** PostgreSQL (via Docker Compose em `infra/`).

- **Qualidade:** ruff, mypy, pytest, eslint, vitest. Código limpo, funções pequenas, sem duplicação, sem otimização prematura, mas sem desperdício de tokens ou chamadas.

---

# REQUISITOS NÃO FUNCIONAIS (obrigatórios)

- **Custo:** cada execução de agente registra tokens e custo; painel/endpoint de gasto total e por agente; teto de gasto configurável com corte automático.

- **Segurança:** guardrails de entrada (detecção de prompt injection, sanitização de mensagens de hóspedes, camareiras e prestadores) e de saída (validação por schema Pydantic, bloqueio de vazamento de dados internos, limites de ações das ferramentas); allowlist de ferramentas por agente; allowlist de destinatários de mensagens; segredos apenas por variável de ambiente.

- **Auditabilidade:** cada fluxo recebe um `run_id`; deve ser possível reconstruir onde começou, por quais agentes/ferramentas passou, o que decidiu e onde terminou (Langfuse + log de auditoria próprio consultável pelo administrador do sistema).

- **Humano no loop:** ações com custo ou envio externo exigem aprovação, conforme a política de autonomia definida acima (ADM sempre aprova a escolha do prestador na sessão do imóvel).

- **Resiliência:** timeouts e lembretes nas esperas por prestador e ADM; o ticket nunca fica parado sem estado visível no painel.

---

# ESTIMATIVA E CONTROLE DE CUSTO

O Planejador deve produzir `docs/COST.md` **antes** de fechar a escolha de modelos e a divisão de sprints, contendo:

1. **Custo por execução de fluxo:** para cada fluxo (roteamento, atendimento comercial, classificação do problema, coleta de prestadores, orçamento e agendamento), listar cada chamada de LLM com agente, modelo candidato, tokens de entrada estimados (prompt + contexto + histórico), tokens de saída estimados, preço por 1M de tokens (consultar a tabela vigente da Featherless; não usar valores de memória) e custo resultante. Considerar retries, chamadas dos guardrails e a interpretação de cada resposta de prestador/ADM. Se a Featherless cobrar por plano e não por token, substituir por consumo de créditos e limite de concorrência.

2. **Custos fora do LLM:** chamadas à Google Places API, mensagens enviadas pelo canal escolhido e hospedagem.

3. **Cenários:** otimista, esperado e pessimista (ex.: conversas longas, retries, tentativas de injection, prestadores que não respondem ou recusam data).

4. **Projeção total:** execuções estimadas por fase (desenvolvimento com mocks, testes automatizados finais com modelo real, ensaio, Demo Day) × custo por execução, comparada ao orçamento e à reserva de 30%.

5. **Escolha de modelo por tarefa:** tabela com o modelo mais barato que atende ao critério de qualidade e uma alternativa de fallback. Tarefas simples (classificação, extração, roteamento, guardrail de entrada) devem usar modelos menores.

6. **Alavancas de economia:** limites de contexto/histórico, `max_tokens` por chamada, cache de respostas e de dados estáticos, resumo de conversas longas, testes e desenvolvimento inicial com LLM mockado por padrão (modelo real apenas nos testes finais marcados e na demo).

7. **Teto e alertas:** limites por execução, por sprint e global; alerta em 50%, 75% e 90% do orçamento; corte automático ao atingir o teto; custo real registrado em cada trace do Langfuse.

8. **Recalibração:** ao fim de cada sprint, o Revisor compara custo estimado vs. real (Langfuse) e o Planejador atualiza o `docs/COST.md` e ajusta o plano se o desvio passar de 25%.

---

# OS 3 AGENTES (crie um arquivo .md para cada um em `/agents/`)

### 1. Planejador (`agents/planner.md`)

Lê o escopo e o estado atual; produz e atualiza o plano; divide em sprints; escreve, para cada task: objetivo, requisitos, arquivos prováveis, dependências, Definition of Done e critérios de aceite testáveis. **Mantém o `docs/COST.md` e o recalibra a cada sprint.** Não escreve código de produção.

### 2. Implementador (`agents/implementer.md`)

Implementa **somente** a task atribuída, na branch da task, seguindo o plano; escreve os testes junto com o código; não altera escopo nem plano (se encontrar problema, registra e devolve ao Planejador). Não faz commit: entrega as mudanças para revisão. **Toda chamada ao LLM define `max_tokens` e modelo, e registra custo.**

### 3. Revisor/Auditor (`agents/reviewer.md`)

Verifica as mudanças contra o DoD e os critérios de aceite; roda lint, tipos e testes; checa segurança, custo e qualidade; só então aprova e faz o **commit atômico** na branch da task (um commit = uma mudança lógica, mensagem em Conventional Commits) e abre o PR para `develop`. Reprova com lista objetiva de correções. **Compara custo real vs. estimado e bloqueia a aprovação se houver chamada ao LLM não prevista ou sem limite de tokens.**

Cada .md deve conter: missão, entradas, saídas, o que pode e o que não pode fazer, checklist, formato de relatório e critérios de passagem para o próximo agente.

---

# REGRAS DE FLUXO

- Ciclo por task: **Planejador → Implementador → Revisor**. Nada é commitado sem aprovação do Revisor; o merge em `develop` é feito pelo dev humano dono da task.

- **Gate de sprint:** uma sprint só começa depois que o plano dela foi revisado e aprovado pelo Revisor (clareza, escopo realista para o tempo, dependências, testabilidade, custo previsto). Uma sprint só termina quando todas as tasks passam e o critério de sprint é atendido.

- Tasks que tocam os mesmos arquivos não podem ser paralelizadas entre devs; o plano deve indicar quais tasks são independentes.

- Sprints devem ser curtas e caber no prazo do hackathon; defina quantas forem necessárias.

---

# DOCUMENTO DE STATUS (fonte da verdade)

Crie `docs/STATUS.md` com, por fase (**Planejamento, Implementação, Validação**) e por sprint/task: estado (não iniciada / em andamento / em revisão / aprovada / bloqueada), responsável (dev e agente), branch, último commit, bloqueios e decisões. Todo agente lê este arquivo antes de agir e o atualiza ao iniciar e ao terminar seu trabalho.

---

# ORGANIZAÇÃO DO REPOSITÓRIO E BRANCHES (4 devs em paralelo)

Defina em `docs/CONTRIBUTING.md` e referencie em todos os `agents/*.md`:

- **Estrutura de pastas:** `backend/`, `frontend/`, `agents/`, `docs/`, `tests/`, `infra/`.

- **Branches:**
  - `main` protegida (só recebe merge de `develop` aprovado, feito por um dev humano definido)
  - `develop` (integração)
  - `feature/<sprint>-<task-id>-<slug>`, `fix/<...>`, `docs/<...>`
  - Uma task = uma branch = um dev/agente dono.

- **Commits e PRs:** commits atômicos em Conventional Commits; PRs pequenos; rebase em `develop` antes do PR.

- **Conflitos e arquivos compartilhados:** regra para resolução de conflitos; alterações em contratos Pydantic, schemas e configs só por meio de task dedicada.

- **Definition of Ready e Definition of Done globais.**

---

# CRITÉRIOS DE AVALIAÇÃO

**Por task:**

- Critérios de aceite verificáveis atendidos e testes passando.

- Cobertura mínima: **70% no código novo**.

- Lint e tipos limpos.

- Guardrails e logging/tracing presentes quando aplicável.

- Sem segredos nem dados pessoais no código ou nos logs (LGPD: telefones de prestadores e dados de hóspedes mascarados); documentação curta atualizada.

- Custo estimado da task registrado, e toda chamada nova ao LLM consta no `docs/COST.md`.

**Por sprint:**

- Demo funcional do incremento e todos os testes verdes.

- Traces no Langfuse do fluxo demonstrado.

- Gasto real dentro de ±25% do estimado e dentro do orçamento da sprint; desvio maior exige justificativa e replanejamento antes da próxima sprint.

- `docs/STATUS.md` atualizado e nenhum item crítico aberto do Revisor.

---

# PLANO DE TESTES

Inclua no plano:

- **Unitários:** schemas, ferramentas, guardrails, regra de urgência × agenda.

- **Integração:** fluxos de agentes com LLM mockado, incluindo os caminhos alternativos: nenhum prestador no DB, prestador sem resposta (timeout), ADM sem resposta, prestador recusa a data, inquilino hospedado vs. imóvel vazio.

- **Segurança:** suíte de prompts maliciosos/injection vindos de hóspede, camareira e prestador.

- **Custo:** validar que o teto por execução e o teto global cortam o fluxo, que os alertas disparam e que o custo registrado no Langfuse bate com a estimativa dentro da margem definida.

- **End-to-end:** cenário principal com os modelos reais (ativados na fase final) e contatos da allowlist/simulador.

- **Validação final para o Demo Day:** checklist, dados de demo (DB de prestadores e agenda pré-populados), ensaio do pitch, plano B caso a API falhe (respostas gravadas/mock), e conferência dos itens de submissão (descrição, vídeo, link testável, material do Demo Day, lista de ferramentas).

---

# ENTREGÁVEIS DESTA ETAPA

1. `agents/planner.md`, `agents/implementer.md`, `agents/reviewer.md`

2. `docs/PLAN.md`: visão, requisitos funcionais e não funcionais, arquitetura em alto nível (os 3 fluxos e a máquina de estados do ticket), sprints, tasks com DoD, plano de testes finais e riscos

3. `docs/COST.md`, `docs/STATUS.md` e `docs/CONTRIBUTING.md` iniciais

4. Lista de perguntas em aberto para os humanos

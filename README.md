# SmartRepair AI — Gestão Inteligente de Imóveis de Temporada

Plataforma de agentes de IA de ponta a ponta para gestores e anfitriões de imóveis de temporada (experiência estilo Airbnb). O sistema atende potenciais hóspedes de forma calorosa até a reserva e resolve problemas de manutenção relatados por inquilinos ou camareiras de ponta a ponta — encontrando, validando, orçando e agendando prestadores de serviço com aprovação humana do anfitrião (ADM).

---

## Arquitetura dos 3 Fluxos Independentes

O produto opera com um **Ponto Único de Chat por Imóvel** (equipado com um roteador barato) e **três fluxos independentes** conectados pelo banco de dados PostgreSQL e pelo `property_id`:

1. **Fluxo A — Aquisição (`Roteador → Nó 1 Comercial → Reserva`):**
   - Tira dúvidas sobre o imóvel de forma calorosa até confirmar a reserva ("temos inquilino").
2. **Fluxo B — Coleta e Validação de Prestadores (`Nó S via APScheduler`):**
   - Job periódico e assíncrono que busca prestadores por categoria/região (Google Places API / fixture), envia mensagem para validar o contato e grava no PostgreSQL **apenas prestadores que confirmaram**.
3. **Fluxo C — Manutenção Ponta a Ponta (`Roteador → Nó 2 Validador → Nó 3 Resolvedor ⇄ ADM / Prestador → Aviso ao Inquilino`):**
   - **Nó 2 (Validador):** Recebe o relato do **inquilino ou da camareira**, faz perguntas de esclarecimento se necessário, classifica categoria, urgência e local no imóvel e gera um ticket estruturado (Pydantic v2).
   - **Nó 3 (Resolvedor em LangGraph):**
     1. Pede orçamento a `N` prestadores validados do DB (sem negociar preço) com controle de timeout.
     2. Notifica o anfitrião (**ADM**) na **sessão exclusiva Agente ⇄ Anfitrião daquele imóvel** e aguarda a escolha humana (*human-in-the-loop*).
     3. Consulta a agenda do imóvel e propõe datas ao prestador escolhido conforme a **urgência** (urgente = o quanto antes, mesmo com hóspede; não urgente = prefere dias sem hóspede).
     4. Recebe a confirmação do dia ("devolutiva do dia") do prestador; se recusar, retorna ao passo 3.
     5. Se houver inquilino hospedado na data, avisa o inquilino sobre o dia da manutenção, registra na agenda e fecha o ticket.

---

## Documentação e Governança (Time de 4 Devs + 3 Agentes de IA)

- **Fonte da verdade do escopo:** [`planejamento2.md`](planejamento2.md)
- **Plano de implementação, arquitetura e sprints:** [`docs/PLAN.md`](docs/PLAN.md)
- **Estimativa, tetos e controle de custos (Featherless + Langfuse):** [`docs/COST.md`](docs/COST.md)
- **Status atual das fases, sprints e tasks:** [`docs/STATUS.md`](docs/STATUS.md)
- **Regras de repositório, branches, commits e DoR/DoD:** [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md)
- **Instruções dos 3 Agentes de Desenvolvimento:**
  - Planejador: [`agents/planner.md`](agents/planner.md)
  - Implementador: [`agents/implementer.md`](agents/implementer.md)
  - Revisor / Auditor: [`agents/reviewer.md`](agents/reviewer.md)

# Custo de inferência — estimativa inicial (2026-11-07)

## Fonte, premissas e regra

Preços públicos da Featherless por **1 milhão de tokens**: [Qwen/Qwen3.5-4B](https://featherless.ai/models/Qwen/Qwen3.5-4B) **US$ 0,10 entrada / 0,20 saída**; [Qwen/Qwen3.5-9B](https://featherless.ai/models/Qwen/Qwen3.5-9B) **US$ 0,17 / 0,25**. O [catálogo de preços](https://featherless.ai/docs/request-pricing-and-credits) explica cobrança separada de entrada/saída e exceções por modelo. Confirmar preço via catálogo ou `/v1/models` imediatamente antes de usar; página de modelo prevalece sobre preço genérico de classe. Valores abaixo são **hipóteses de dimensionamento**, não medição. Fórmula por chamada: `(tokens_entrada × preço_entrada + tokens_saída × preço_saída) / 1.000.000`. Sem desconto de cache assumido. Não inclui impostos, Places, hospedagem ou mensageria.

O [plano Developer público](https://featherless.ai/docs/billing) começa em US$ 50/mês; o time informou **US$ 25 em créditos**. P0 deve confirmar que esses créditos são utilizáveis na API e por todos os devs/agentes. Sem essa confirmação, acesso real é bloqueio, não autorização para compra.

## Qualidade e escolha provisória por tarefa

Critério de aceite antes de fixar modelos: 20 exemplos em português por tarefa, ≥95% de schema válido e classificação correta para dados essenciais; 0 contratações/agendamentos sem ADM; 0 vazamentos nos prompts maliciosos de teste. Escolher o menor custo entre modelos que passarem. Os candidatos abaixo **ainda não foram validados**.

| Tarefa | Candidato | Fallback | Motivo / limite |
| --- | --- | --- | --- |
| Guardrail de entrada e extração/classificação | `Qwen/Qwen3.5-4B` | `Qwen/Qwen3.5-9B` | Tarefas curtas; regra determinística de tamanho/allowlist vem antes do LLM. |
| Comercial caloroso | `Qwen/Qwen3.5-9B` | `Qwen/Qwen3.5-27B` | Validar tom, português e encaminhamento. |
| Síntese/negociação | `Qwen/Qwen3.5-9B` | `Qwen/Qwen3.5-27B` | Validar comparação de cotações e política ADM. |
| Agendamento após escolha | `Qwen/Qwen3.5-4B` | `Qwen/Qwen3.5-9B` | Agenda e conflito decididos por código; LLM só redige confirmação. |
| Coleta de prestadores | sem LLM | — | Busca/validação por ferramenta e allowlist. |

O fallback 27B tem preço de classe publicado de US$ 0,30/2,40 por 1M na [tabela Featherless](https://featherless.ai/docs/request-pricing-and-credits); verificar a página do ID exato antes de ativá-lo. **Não ativar fallback sem reserva de custo e registro da chamada.**

## Custo por execução de fluxo — cenário base

Tokens de entrada incluem prompt, instruções, contexto e histórico limitado. `max_tokens` sugerido é o teto de saída, igual ou acima da estimativa; a implementação precisa fixá-lo por chamada. `run_id` agrupa tudo. O guardrail de prestador roda uma vez para cada uma das cinco respostas simuladas; o limite de ferramentas impede envio externo não aprovado.

| Fluxo / chamada | Agente/modelo | Entrada | Saída estimada / `max_tokens` | US$/1M entrada / saída | Custo US$ |
| --- | --- | ---: | ---: | ---: | ---: |
| Atendimento: checagem de entrada | Guardrail, 4B | 250 | 40 / 64 | 0,10 / 0,20 | 0,000033 |
| Atendimento: resposta/roteamento | Comercial, 9B | 900 | 180 / 256 | 0,17 / 0,25 | 0,000198 |
| Classificação: checagem de entrada | Guardrail, 4B | 300 | 40 / 64 | 0,10 / 0,20 | 0,000038 |
| Classificação: ticket estruturado | Validador, 4B | 700 | 140 / 192 | 0,10 / 0,20 | 0,000098 |
| Coleta: top 5 e contato validado | Tool S, sem LLM | 0 | 0 | 0 / 0 | 0 |
| Negociação: checar 5 respostas | Guardrail, 4B | 1.250 | 200 / 64 cada | 0,10 / 0,20 | 0,000165 |
| Negociação: pedido de orçamento | Resolvedor, 9B | 1.100 | 220 / 256 | 0,17 / 0,25 | 0,000242 |
| Negociação: síntese ao ADM | Resolvedor, 9B | 1.500 | 260 / 320 | 0,17 / 0,25 | 0,000320 |
| Agendamento: confirmação após ADM | Resolvedor, 4B | 500 | 120 / 160 | 0,10 / 0,20 | 0,000074 |
| **Fluxo completo** | | | | | **0,001168** |

Subtotais: atendimento **0,000231**; classificação **0,000136**; coleta **0**; negociação **0,000727**; agendamento **0,000074**. Se o atendimento for apenas dúvida, o fluxo termina após atendimento. Retry máximo **1** por chamada, apenas para erro transitório/schema inválido, condicionado ao teto. Respostas de guardrail podem bloquear antes de chamadas posteriores; a tabela considera passagem normal.

## Cenários

| Cenário | Hipótese | Custo/fluxo completo |
| --- | --- | ---: |
| Otimista | Base acima, sem retry nem cache faturado | US$ 0,001168 |
| Esperado | Base + 15% de chamadas/tokens por esclarecimento e retry médio | **US$ 0,001343** |
| Pessimista | Entradas/saídas 2×, um retry completo e checagens extras por injection; fator conservador 5× | **US$ 0,005840** |

Pior caso não autoriza gasto ilimitado: `max_tokens`, histórico e teto por execução cortam antes da chamada que excederia a reserva. Dados inválidos/injection podem gerar menos chamadas, mas são orçados pelo cenário pessimista.

## Projeção compartilhada e reserva

US$ **25,00** totais. Reserva obrigatória **US$ 7,50** (30%) fica indisponível até ensaio e Demo Day; desenvolvimento/testes anteriores usam no máximo **US$ 17,50**. O envelope dos agentes de desenvolvimento inclui prompts de Planejador, Implementador, Revisor e uso direto dos quatro humanos; é uma provisão, a refinar com seus modelos/tokens reais em P0. Testes automatizados usam mock por padrão.

| Fase | Fluxos reais × esperado | Produto US$ | Provisão agentes de desenvolvimento US$ | Total previsto US$ | Envelope máximo |
| --- | ---: | ---: | ---: | ---: | ---: |
| Desenvolvimento S0–S2 | 200 × 0,001343 | 0,269 | 8,00 | 8,269 | 17,50 antes da reserva |
| Testes marcados com modelo real | 80 × 0,001343 | 0,107 | 2,00 | 2,107 | incluído nos 17,50 |
| **Subtotal antes da reserva** | **280** | **0,376** | **10,00** | **10,376** | **17,50** |
| Ensaio S3 | 20 × 0,001343 | 0,027 | 1,50 | 1,527 | reserva de 7,50 |
| Demo Day S3 | 20 × 0,001343 | 0,027 | 1,50 | 1,527 | reserva de 7,50 |
| **Total previsto** | **320** | **0,430** | **13,00** | **13,430** | **25,00** |

Mesmo 320 fluxos no cenário pessimista somariam US$ 1,869 de produto, mas a maior incerteza é o uso dos agentes de desenvolvimento. Cada dev reporta saldo gasto diariamente e antes de qualquer teste real. Saldo não gasto da reserva permanece reservado; não migra automaticamente para desenvolvimento.

## Tetos, alertas e economia

- Teto inicial **US$ 0,03 por `run_id`**; tetos de sprint: S0 US$ 1,00, S1 US$ 5,00, S2 US$ 11,50 (soma pré-reserva US$ 17,50), S3 US$ 7,50 somente ensaio/Demo. Teto global US$ 25,00. Ajustar envelopes após medir consumo dos agentes de desenvolvimento; nenhum ajuste pode tocar reserva antes de S3.
- Alertas globais em **US$ 12,50 (50%)**, **18,75 (75%)**, **22,50 (90%)** e equivalentes por sprint; log/endpoint expõe total e por agente. Pré-reservar custo máximo da chamada com `max_tokens` e limite de entrada; cortar automaticamente se exceder teto por run, sprint, fase ou global. Reconciliar uso real ao final, inclusive retry; marcar custo desconhecido como bloqueio conservador.
- Limitar histórico a últimas mensagens + resumo, entrada por chamada e `max_tokens` da tabela; cache de respostas seguras e dados estáticos; resumir conversa longa; não repetir chamada após erro de política; timeout e retry único. Cache deve preservar `run_id` e registrar custo zero em hit.
- Cada trace Langfuse registra tokens de entrada/saída, preço vigente, custo calculado, agente, modelo, `run_id`, retry e orçamento restante; comparar com ledger próprio e preço faturado. Nunca registrar segredo ou mensagem completa sensível.

## Recalibração obrigatória

Ao fim de cada sprint, Revisor exporta consumo real do Langfuse e compara por tarefa/modelo com esta estimativa. Desvio absoluto **>25%** exige causa (histórico, retry, preço, fallback, volume), justificativa e `COST.md` atualizado pelo Planejador antes do gate seguinte. Qualquer chamada LLM nova, sem modelo, sem `max_tokens`, sem trace ou fora desta tabela bloqueia aprovação. Registrar versão/data do preço consultado e a decisão de modelo após bateria de qualidade.

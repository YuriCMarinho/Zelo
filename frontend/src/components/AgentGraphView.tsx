import { useState, useMemo } from 'react'
import type { Property } from '../contracts'
import { propertyUrl } from '../routes'

export interface AgentNode {
  id: string
  label: string
  sublabel: string
  type: 'property' | 'router' | 'commercial' | 'validator' | 'collector' | 'resolver'
  propertyId?: string
  x: number
  y: number
  radius: number
  description: string
  ioContract: {
    input: string
    output: string
  }
  modelName: string
  phaseNumber?: string
  defaultStatus: 'idle' | 'running' | 'waiting' | 'success'
  langfuse: {
    traceId: string
    spanName: string
    tokensIn: number
    tokensOut: number
    costUsd: number
    latencyMs: number
    isMock: boolean
  }
}

interface AgentGraphViewProps {
  navigate: (url: string) => void
  propertiesList: Property[]
}

const moneyUsd = (value: number) => `$${value.toFixed(6)}`

const PROPERTY_FLOW_SUMMARIES: Record<
  string,
  { statusLabel: string; summary: string; focusNodeId: string; tone: 'waiting' | 'success' | 'idle' }
> = {
  all: {
    statusLabel: '4 imóveis monitorados',
    summary: '1 chamado aguarda aprovação humana na Casa Aurora; 3 imóveis operam em triagem automática.',
    focusNodeId: 'node-3-adm',
    tone: 'waiting',
  },
  'casa-aurora': {
    statusLabel: 'Aguardando aprovação do anfitrião (Passo 3.2)',
    summary: 'Chuveiro sem água quente · 3 orçamentos coletados pelo Nó 3 aguardam sua escolha para agendar.',
    focusNodeId: 'node-3-adm',
    tone: 'waiting',
  },
  'loft-jardim': {
    statusLabel: 'Atendimento comercial ativo (Nó 1)',
    summary: 'Dúvidas de pré-reserva e revisão preventiva de ar-condicionado respondidas sem pendências.',
    focusNodeId: 'node-1',
    tone: 'success',
  },
  'vila-areia': {
    statusLabel: 'Operação normal · Sem chamados abertos',
    summary: 'Roteador em escuta para novas mensagens de hóspedes ou camareira.',
    focusNodeId: 'prop-vila-areia',
    tone: 'idle',
  },
  'prop-portodigital-04': {
    statusLabel: 'Atendimento comercial ativo (Nó 1)',
    summary: 'Consultas sobre Wi-Fi dedicado de 500Mbps e check-in autônomo atendidas pelo Nó 1.',
    focusNodeId: 'node-1',
    tone: 'success',
  },
}

export function AgentGraphView({ navigate, propertiesList }: AgentGraphViewProps) {
  const [selectedPropertyFilter, setSelectedPropertyFilter] = useState<string>('all')
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>('node-3-adm')
  const [copiedTrace, setCopiedTrace] = useState(false)
  const [isGuideOpen, setIsGuideOpen] = useState(true)

  const propList = useMemo(() => propertiesList.slice(0, 4), [propertiesList])

  const nodes: AgentNode[] = useMemo(
    () => [
      // Coluna 1: Imóveis (X: 96)
      {
        id: 'prop-casa-aurora',
        propertyId: 'casa-aurora',
        label: 'Casa Aurora',
        sublabel: 'Praia do Futuro · CE',
        type: 'property',
        x: 96,
        y: 115,
        radius: 28,
        description:
          'Imóvel com chamado elétrico em andamento (chuveiro da suíte). O hóspede relatou no chat único e o fluxo aguarda decisão do anfitrião.',
        ioContract: {
          input: 'Mensagem do hóspede ou camareira',
          output: 'Evento autenticado com property_id',
        },
        modelName: 'Canal Único do Imóvel',
        defaultStatus: 'waiting',
        langfuse: {
          traceId: 'run-demo-001',
          spanName: 'imovel.casa-aurora.chat',
          tokensIn: 320,
          tokensOut: 60,
          costUsd: 0.000044,
          latencyMs: 140,
          isMock: false,
        },
      },
      {
        id: 'prop-loft-jardim',
        propertyId: 'loft-jardim',
        label: 'Loft Jardim',
        sublabel: 'Meireles · CE',
        type: 'property',
        x: 96,
        y: 230,
        radius: 28,
        description:
          'Loft urbano com reservas confirmadas e atendimento comercial automatizado para dúvidas de check-in.',
        ioContract: {
          input: 'Dúvida sobre estadia ou manutenção',
          output: 'Sessão vinculada ao Loft Jardim',
        },
        modelName: 'Canal Único do Imóvel',
        defaultStatus: 'idle',
        langfuse: {
          traceId: 'run-loft-002',
          spanName: 'imovel.loft-jardim.chat',
          tokensIn: 180,
          tokensOut: 45,
          costUsd: 0.000027,
          latencyMs: 110,
          isMock: true,
        },
      },
      {
        id: 'prop-vila-areia',
        propertyId: 'vila-areia',
        label: 'Vila Areia',
        sublabel: 'Cumbuco · CE',
        type: 'property',
        x: 96,
        y: 345,
        radius: 28,
        description:
          'Imóvel de temporada à beira-mar com agenda ativa e monitoramento contínuo de solicitações.',
        ioContract: {
          input: 'Mensagem no chat do imóvel',
          output: 'Sessão vinculada à Vila Areia',
        },
        modelName: 'Canal Único do Imóvel',
        defaultStatus: 'idle',
        langfuse: {
          traceId: 'run-vila-003',
          spanName: 'imovel.vila-areia.chat',
          tokensIn: 90,
          tokensOut: 25,
          costUsd: 0.000014,
          latencyMs: 95,
          isMock: true,
        },
      },
      {
        id: 'prop-portodigital',
        propertyId: 'prop-portodigital-04',
        label: 'Studio Tech',
        sublabel: 'Porto Digital · PE',
        type: 'property',
        x: 96,
        y: 460,
        radius: 28,
        description:
          'Studio no Recife Antigo voltado a estadias de trabalho remoto, com respostas rápidas sobre conectividade e acesso.',
        ioContract: {
          input: 'Pergunta de hóspede ou relato técnico',
          output: 'Sessão vinculada ao Studio Tech',
        },
        modelName: 'Canal Único do Imóvel',
        defaultStatus: 'idle',
        langfuse: {
          traceId: 'run-recife-004',
          spanName: 'imovel.recife.chat',
          tokensIn: 210,
          tokensOut: 50,
          costUsd: 0.000031,
          latencyMs: 125,
          isMock: true,
        },
      },

      // Coluna 2: Triagem & Coleta (X: 280)
      {
        id: 'node-router',
        label: 'Roteador',
        sublabel: 'Guardrail + 4B',
        type: 'router',
        x: 280,
        y: 285,
        radius: 32,
        phaseNumber: 'R',
        description:
          'Filtra tentativas de prompt injection e classifica se a mensagem é uma dúvida comercial (Fluxo A) ou um problema de manutenção (Fluxo C).',
        ioContract: {
          input: 'Texto sanitizado + perfil do remetente',
          output: 'Rota determinística: Nó 1 ou Nó 2',
        },
        modelName: 'Qwen/Qwen3.5-4B (Featherless)',
        defaultStatus: 'success',
        langfuse: {
          traceId: 'run-demo-001',
          spanName: 'router.intent_classification',
          tokensIn: 550,
          tokensOut: 70,
          costUsd: 0.000069,
          latencyMs: 310,
          isMock: false,
        },
      },
      {
        id: 'node-s',
        label: 'Nó S: Coletor',
        sublabel: 'APScheduler',
        type: 'collector',
        x: 280,
        y: 115,
        radius: 28,
        phaseNumber: 'S',
        description:
          'Job periódico assíncrono que busca prestadores por região, valida disponibilidade de atendimento e grava no banco apenas profissionais confirmados.',
        ioContract: {
          input: 'Categoria + cidade do imóvel',
          output: 'Prestadores validados no PostgreSQL',
        },
        modelName: 'APScheduler + Qwen3.5-4B',
        defaultStatus: 'success',
        langfuse: {
          traceId: 'run-cron-batch-08',
          spanName: 'provider_collector.validation_job',
          tokensIn: 2250,
          tokensOut: 350,
          costUsd: 0.000295,
          latencyMs: 1840,
          isMock: true,
        },
      },

      // Coluna 3: Especialistas (X: 465)
      {
        id: 'node-1',
        label: 'Nó 1: Comercial',
        sublabel: 'Pré-Reserva · 9B',
        type: 'commercial',
        x: 465,
        y: 195,
        radius: 30,
        phaseNumber: '1',
        description:
          'Responde dúvidas sobre regras, comodidades e disponibilidade do imóvel de forma acolhedora até a confirmação da reserva.',
        ioContract: {
          input: 'Pergunta do potencial hóspede + FAQ do imóvel',
          output: 'Resposta contextualizada + registro de reserva',
        },
        modelName: 'Qwen/Qwen3.5-9B (Featherless)',
        defaultStatus: 'success',
        langfuse: {
          traceId: 'run-comercial-101',
          spanName: 'commercial.guest_inquiry',
          tokensIn: 2400,
          tokensOut: 540,
          costUsd: 0.000543,
          latencyMs: 820,
          isMock: true,
        },
      },
      {
        id: 'node-2',
        label: 'Nó 2: Validador',
        sublabel: 'Triagem Pydantic',
        type: 'validator',
        x: 465,
        y: 365,
        radius: 30,
        phaseNumber: '2',
        description:
          'Extrai categoria técnica, urgência e cômodo afetado a partir do relato do hóspede ou camareira, gerando o chamado estruturado.',
        ioContract: {
          input: 'Relato de problema no imóvel',
          output: 'Ticket estruturado (Pydantic v2)',
        },
        modelName: 'Qwen/Qwen3.5-4B (Featherless)',
        defaultStatus: 'success',
        langfuse: {
          traceId: 'run-demo-001',
          spanName: 'validator.ticket_structuring',
          tokensIn: 1400,
          tokensOut: 280,
          costUsd: 0.000196,
          latencyMs: 460,
          isMock: false,
        },
      },

      // Coluna 4: Resolução LangGraph Nó 3 (X: 645 a 965)
      {
        id: 'node-3-quotes',
        label: '3.1 Cotações',
        sublabel: 'Coleta Paralela',
        type: 'resolver',
        x: 645,
        y: 365,
        radius: 28,
        phaseNumber: '3.1',
        description:
          'Aciona até 3 prestadores validados da categoria na região do imóvel e aguarda os orçamentos com controle de timeout.',
        ioContract: {
          input: 'Ticket aberto + prestadores homologados',
          output: 'Lista de orçamentos com preço e prazo',
        },
        modelName: 'LangGraph + Template Determinístico',
        defaultStatus: 'success',
        langfuse: {
          traceId: 'run-demo-001',
          spanName: 'resolver_graph.request_quotes',
          tokensIn: 600,
          tokensOut: 140,
          costUsd: 0.000088,
          latencyMs: 190,
          isMock: false,
        },
      },
      {
        id: 'node-3-adm',
        label: '3.2 Decisão ADM',
        sublabel: 'Aprovação Humana',
        type: 'resolver',
        x: 645,
        y: 470,
        radius: 32,
        phaseNumber: '3.2',
        description:
          'Sintetiza os orçamentos recebidos e pausa o grafo (interrupt) até que o anfitrião aprove explicitamente o prestador.',
        ioContract: {
          input: 'Orçamentos comparados (preço, nota, janela)',
          output: 'Prestador aprovado pelo anfitrião',
        },
        modelName: 'Qwen/Qwen3.5-9B (Featherless)',
        defaultStatus: 'waiting',
        langfuse: {
          traceId: 'run-demo-001',
          spanName: 'resolver_graph.await_adm_approval',
          tokensIn: 1400,
          tokensOut: 260,
          costUsd: 0.000303,
          latencyMs: 650,
          isMock: false,
        },
      },
      {
        id: 'node-3-schedule',
        label: '3.3 Agendamento',
        sublabel: 'Urgência × Agenda',
        type: 'resolver',
        x: 805,
        y: 470,
        radius: 28,
        phaseNumber: '3.3',
        description:
          'Cruza a urgência do reparo com o calendário de ocupação: chamados urgentes priorizam a primeira janela; normais priorizam dias livres.',
        ioContract: {
          input: 'Urgência do ticket + calendário de reservas',
          output: 'Proposta de data enviada ao prestador',
        },
        modelName: 'Regra Determinística (Zero Tokens)',
        defaultStatus: 'idle',
        langfuse: {
          traceId: 'run-demo-001',
          spanName: 'resolver_graph.calculate_schedule',
          tokensIn: 0,
          tokensOut: 0,
          costUsd: 0.0,
          latencyMs: 25,
          isMock: true,
        },
      },
      {
        id: 'node-3-confirm',
        label: '3.4 Devolutiva',
        sublabel: 'Confirmação do Dia',
        type: 'resolver',
        x: 805,
        y: 365,
        radius: 28,
        phaseNumber: '3.4',
        description:
          'Valida o aceite do prestador para a data proposta. Se recusar, retorna ao passo 3.3 para ofertar a próxima janela disponível.',
        ioContract: {
          input: 'Resposta do prestador sobre a data',
          output: 'Data confirmada ou recálculo de janela',
        },
        modelName: 'Guardrail Determinístico + 4B',
        defaultStatus: 'idle',
        langfuse: {
          traceId: 'run-demo-001',
          spanName: 'resolver_graph.provider_confirmation',
          tokensIn: 650,
          tokensOut: 100,
          costUsd: 0.000085,
          latencyMs: 310,
          isMock: true,
        },
      },
      {
        id: 'node-3-notify',
        label: '3.5 Aviso & Fim',
        sublabel: 'Conclusão do Ciclo',
        type: 'resolver',
        x: 965,
        y: 365,
        radius: 28,
        phaseNumber: '3.5',
        description:
          'Notifica o hóspede caso esteja no imóvel na data agendada, bloqueia a janela no calendário e encerra o chamado com trilha auditável.',
        ioContract: {
          input: 'Agendamento confirmado',
          output: 'Aviso enviado no chat + Ticket RESOLVED',
        },
        modelName: 'Qwen/Qwen3.5-4B (Featherless)',
        defaultStatus: 'idle',
        langfuse: {
          traceId: 'run-demo-001',
          spanName: 'resolver_graph.notify_and_close',
          tokensIn: 450,
          tokensOut: 110,
          costUsd: 0.000067,
          latencyMs: 240,
          isMock: true,
        },
      },
    ],
    [],
  )

  const edges = useMemo(
    () => [
      { from: 'prop-casa-aurora', to: 'node-router', activeFor: ['all', 'casa-aurora'] },
      { from: 'prop-loft-jardim', to: 'node-router', activeFor: ['all', 'loft-jardim'] },
      { from: 'prop-vila-areia', to: 'node-router', activeFor: ['all', 'vila-areia'] },
      { from: 'prop-portodigital', to: 'node-router', activeFor: ['all', 'prop-portodigital-04'] },
      { from: 'node-router', to: 'node-1', activeFor: ['all', 'loft-jardim', 'prop-portodigital-04'] },
      { from: 'node-router', to: 'node-2', activeFor: ['all', 'casa-aurora'] },
      { from: 'node-s', to: 'node-3-quotes', dashed: true, activeFor: ['all', 'casa-aurora'] },
      { from: 'node-2', to: 'node-3-quotes', activeFor: ['all', 'casa-aurora'] },
      { from: 'node-3-quotes', to: 'node-3-adm', activeFor: ['all', 'casa-aurora'] },
      { from: 'node-3-adm', to: 'node-3-schedule', activeFor: ['all', 'casa-aurora'] },
      { from: 'node-3-schedule', to: 'node-3-confirm', activeFor: ['all', 'casa-aurora'] },
      { from: 'node-3-confirm', to: 'node-3-schedule', curveBack: true, dashed: true, activeFor: ['all'] },
      { from: 'node-3-confirm', to: 'node-3-notify', activeFor: ['all', 'casa-aurora'] },
    ],
    [],
  )

  const activeNode = useMemo(() => {
    return nodes.find((n) => n.id === selectedNodeId) ?? nodes[0]!
  }, [nodes, selectedNodeId])

  const activeFilterSummary = PROPERTY_FLOW_SUMMARIES[selectedPropertyFilter] ?? PROPERTY_FLOW_SUMMARIES.all!

  function handleSelectPropertyFilter(filterId: string) {
    setSelectedPropertyFilter(filterId)
    const summary = PROPERTY_FLOW_SUMMARIES[filterId]
    if (summary) {
      setSelectedNodeId(summary.focusNodeId)
    }
  }

  const copyTraceId = (traceId: string) => {
    navigator.clipboard?.writeText(traceId)
    setCopiedTrace(true)
    setTimeout(() => setCopiedTrace(false), 2000)
  }

  return (
    <div className="agent-graph-page" aria-label="Visualização do Grafo de Agentes e Imóveis">
      {/* Cabeçalho direto e sem ruído */}
      <div className="agent-graph-header">
        <div className="agent-graph-title-row">
          <div>
            <h1>Grafo de Fases dos Agentes & Imóveis</h1>
            <p className="agent-graph-lead">
              Selecione um imóvel para destacar sua rota ativa ou clique em qualquer bolinha para inspecionar entradas,
              saídas e telemetria no <strong>Langfuse</strong>.
            </p>
          </div>
          <button
            type="button"
            className="guide-toggle-btn"
            onClick={() => setIsGuideOpen((prev) => !prev)}
            aria-expanded={isGuideOpen}
          >
            Como funciona a Observabilidade com Langfuse nesta aplicação?
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
              style={{ transform: isGuideOpen ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s ease' }}
            >
              <polyline points="6 9 12 15 18 9" />
            </svg>
          </button>
        </div>

        {/* Barra de filtro por imóvel + resumo contextual imediato */}
        <div className="graph-filter-container">
          <div className="filter-pill-group" role="radiogroup" aria-label="Filtrar imóvel no grafo">
            <button
              type="button"
              className={`filter-pill ${selectedPropertyFilter === 'all' ? 'active' : ''}`}
              onClick={() => handleSelectPropertyFilter('all')}
            >
              Todos os Imóveis
            </button>
            {propList.map((p) => (
              <button
                key={p.id}
                type="button"
                className={`filter-pill ${selectedPropertyFilter === p.id ? 'active' : ''}`}
                onClick={() => handleSelectPropertyFilter(p.id)}
              >
                {p.title}
              </button>
            ))}
          </div>

          <div className="filter-context-strip" aria-live="polite">
            <span className={`status-indicator indicator-${activeFilterSummary.tone}`} />
            <strong>{activeFilterSummary.statusLabel}:</strong>
            <span>{activeFilterSummary.summary}</span>
          </div>
        </div>
      </div>

      {/* Faixa didática do Langfuse (sem cartões aninhados) */}
      {isGuideOpen && (
        <section className="langfuse-guide-strip" aria-label="Arquitetura de observabilidade Langfuse">
          <div className="langfuse-strip-item">
            <span className="step-tag">1. Traces & Spans</span>
            <p>
              Cada atendimento gera um <code>Trace</code> único (<code>run_id</code>). Cada fase do grafo executa em um{' '}
              <code>Span</code> isolado com tempo de início e fim.
            </p>
          </div>
          <div className="langfuse-strip-item">
            <span className="step-tag">2. Mascaramento LGPD</span>
            <p>
              Antes do envio ao Langfuse, <code>mask_dict_pii()</code> sanitiza CPFs, telefones, chaves Pix e e-mails
              em entradas e saídas.
            </p>
          </div>
          <div className="langfuse-strip-item">
            <span className="step-tag">3. Custo por Token</span>
            <p>
              Custo calculado por chamada conforme a tabela Featherless (<code>Qwen3.5-4B</code> na triagem;{' '}
              <code>Qwen3.5-9B</code> na síntese ao anfitrião).
            </p>
          </div>
          <div className="langfuse-strip-item">
            <span className="step-tag">4. Ativação no .env</span>
            <p>
              Defina <code>LANGFUSE_PUBLIC_KEY</code>, <code>LANGFUSE_SECRET_KEY</code> e <code>LANGFUSE_HOST</code> em{' '}
              <code>backend/.env</code>. Sem chaves, opera em modo offline.
            </p>
          </div>
        </section>
      )}

      {/* Layout Principal: Canvas + Inspetor Lateral */}
      <div className="graph-layout">
        <div className="graph-canvas-wrapper" aria-label="Canvas interativo do grafo">
          <div className="graph-canvas-legend">
            <span>
              <i className="legend-dot prop-dot" /> Imóvel (Origem)
            </span>
            <span>
              <i className="legend-dot router-dot" /> Etapa Concluída / Pronta
            </span>
            <span>
              <i className="legend-dot resolver-dot" /> Aguardando Decisão Humana (Interrupt)
            </span>
            <span className="legend-hint">Clique em qualquer bolinha para inspecionar</span>
          </div>

          <svg viewBox="0 0 1060 540" className="agent-graph-svg" role="img" aria-label="Diagrama do Grafo dos Agentes">
            <defs>
              <marker
                id="arrow"
                viewBox="0 0 10 10"
                refX="23"
                refY="5"
                markerWidth="5.5"
                markerHeight="5.5"
                orient="auto-start-reverse"
              >
                <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#17323A" opacity="0.45" />
              </marker>
              <marker
                id="arrow-active"
                viewBox="0 0 10 10"
                refX="23"
                refY="5"
                markerWidth="6"
                markerHeight="6"
                orient="auto-start-reverse"
              >
                <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#F2A541" />
              </marker>
            </defs>

            {/* Guias de colunas arquiteturais */}
            <g className="graph-stage-guides" aria-hidden="true">
              <line x1="190" y1="28" x2="190" y2="515" stroke="rgba(23, 50, 58, 0.08)" strokeDasharray="4,6" />
              <line x1="372" y1="28" x2="372" y2="515" stroke="rgba(23, 50, 58, 0.08)" strokeDasharray="4,6" />
              <line x1="555" y1="28" x2="555" y2="515" stroke="rgba(23, 50, 58, 0.08)" strokeDasharray="4,6" />

              <text x="96" y="34" textAnchor="middle" fill="rgba(23, 50, 58, 0.55)" fontSize="10" fontWeight="700" letterSpacing="0.08em">
                1. IMÓVEIS
              </text>
              <text x="280" y="34" textAnchor="middle" fill="rgba(23, 50, 58, 0.55)" fontSize="10" fontWeight="700" letterSpacing="0.08em">
                2. TRIAGEM & COLETA
              </text>
              <text x="465" y="34" textAnchor="middle" fill="rgba(23, 50, 58, 0.55)" fontSize="10" fontWeight="700" letterSpacing="0.08em">
                3. ESPECIALISTAS
              </text>
              <text x="805" y="34" textAnchor="middle" fill="rgba(23, 50, 58, 0.55)" fontSize="10" fontWeight="700" letterSpacing="0.08em">
                4. RESOLUÇÃO LANGGRAPH (NÓ 3)
              </text>
            </g>

            {/* Conexões (Edges) */}
            {edges.map((edge, idx) => {
              const sourceNode = nodes.find((n) => n.id === edge.from)
              const targetNode = nodes.find((n) => n.id === edge.to)
              if (!sourceNode || !targetNode) return null

              const isEdgeActive =
                selectedPropertyFilter === 'all' || edge.activeFor.includes(selectedPropertyFilter)

              const dx = targetNode.x - sourceNode.x
              const pathD = edge.curveBack
                ? `M ${sourceNode.x} ${sourceNode.y} C ${sourceNode.x + 34} ${sourceNode.y + 52}, ${targetNode.x + 34} ${targetNode.y - 52}, ${targetNode.x} ${targetNode.y}`
                : `M ${sourceNode.x} ${sourceNode.y} C ${sourceNode.x + dx * 0.5} ${sourceNode.y}, ${sourceNode.x + dx * 0.5} ${targetNode.y}, ${targetNode.x} ${targetNode.y}`

              return (
                <g key={`edge-${idx}`} className={`graph-edge ${isEdgeActive ? 'active' : 'dimmed'}`}>
                  <path
                    d={pathD}
                    fill="none"
                    stroke={isEdgeActive ? '#F2A541' : 'rgba(23, 50, 58, 0.2)'}
                    strokeWidth={isEdgeActive ? 2.2 : 1.5}
                    strokeDasharray={edge.dashed ? '5,5' : undefined}
                    markerEnd={isEdgeActive ? 'url(#arrow-active)' : 'url(#arrow)'}
                  />
                </g>
              )
            })}

            {/* Nós ("bolinhas") */}
            {nodes.map((node) => {
              const isSelected = selectedNodeId === node.id
              const isPropertyMatch =
                selectedPropertyFilter === 'all' ||
                (node.propertyId && node.propertyId === selectedPropertyFilter) ||
                (node.type !== 'property' &&
                  (selectedPropertyFilter === 'casa-aurora'
                    ? node.id !== 'node-1'
                    : selectedPropertyFilter === 'loft-jardim' || selectedPropertyFilter === 'prop-portodigital-04'
                      ? node.id === 'node-router' || node.id === 'node-1'
                      : node.id === 'node-router'))

              const isWaiting = node.defaultStatus === 'waiting' && isPropertyMatch

              let strokeColor = '#17323A'
              let fillColor = '#FFFFFF'

              if (node.type === 'property') {
                fillColor = '#F6F3EE'
                strokeColor = '#17323A'
              } else if (node.defaultStatus === 'waiting') {
                strokeColor = '#F2A541'
                fillColor = '#FFFDF9'
              }

              if (isSelected) {
                strokeColor = '#F2A541'
              }

              return (
                <g
                  key={node.id}
                  className={`graph-node-group ${isSelected ? 'selected' : ''} ${!isPropertyMatch ? 'dimmed' : ''}`}
                  onClick={() => setSelectedNodeId(node.id)}
                  style={{ cursor: 'pointer' }}
                  role="button"
                  tabIndex={0}
                  aria-label={`Selecionar nó ${node.label}`}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') setSelectedNodeId(node.id)
                  }}
                >
                  {isWaiting && (
                    <circle
                      cx={node.x}
                      cy={node.y}
                      r={node.radius + 9}
                      fill="none"
                      stroke="#F2A541"
                      strokeWidth="2"
                      opacity="0.65"
                      className="pulse-halo"
                    />
                  )}

                  <circle
                    cx={node.x}
                    cy={node.y}
                    r={node.radius}
                    fill={fillColor}
                    stroke={strokeColor}
                    strokeWidth={isSelected ? 3.5 : 2}
                    className="node-circle"
                  />

                  {node.phaseNumber && (
                    <text
                      x={node.x}
                      y={node.y + 4}
                      textAnchor="middle"
                      fill="#17323A"
                      fontSize="12.5"
                      fontWeight="700"
                    >
                      {node.phaseNumber}
                    </text>
                  )}

                  {node.type === 'property' && (
                    <g transform={`translate(${node.x - 8}, ${node.y - 8})`} aria-hidden="true">
                      <path
                        d="M2 7.5L8 2.5L14 7.5V13.5C14 14.05 13.55 14.5 13 14.5H3C2.45 14.5 2 14.05 2 13.5V7.5Z"
                        fill="none"
                        stroke="#17323A"
                        strokeWidth="1.6"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </g>
                  )}

                  <text
                    x={node.x}
                    y={node.y + node.radius + 15}
                    textAnchor="middle"
                    fill="#17323A"
                    fontSize="12"
                    fontWeight="600"
                  >
                    {node.label}
                  </text>

                  <text
                    x={node.x}
                    y={node.y + node.radius + 28}
                    textAnchor="middle"
                    fill="rgba(23, 50, 58, 0.65)"
                    fontSize="10"
                  >
                    {node.sublabel}
                  </text>
                </g>
              )
            })}
          </svg>
        </div>

        {/* Painel Lateral Didático (Sem aninhamento de cartões) */}
        <aside className="graph-drawer" aria-label="Detalhes do nó selecionado e telemetria">
          <div className="drawer-header">
            <div>
              <div className="drawer-status-line">
                <span
                  className={`status-indicator ${
                    activeNode.defaultStatus === 'waiting'
                      ? 'indicator-waiting'
                      : activeNode.defaultStatus === 'success'
                        ? 'indicator-success'
                        : 'indicator-idle'
                  }`}
                />
                <span className="drawer-status-text">
                  {activeNode.defaultStatus === 'waiting'
                    ? 'Aguardando decisão humana'
                    : activeNode.defaultStatus === 'success'
                      ? 'Ativo e operacional'
                      : 'Em escuta'}
                </span>
              </div>
              <h2>{activeNode.label}</h2>
              <span className="drawer-sublabel">{activeNode.sublabel}</span>
            </div>
          </div>

          <div className="drawer-content">
            {/* Explicação direta + Contrato de Entrada/Saída */}
            <div className="drawer-section">
              <p className="drawer-description">{activeNode.description}</p>
              <dl className="io-contract-list">
                <div>
                  <dt>Entrada</dt>
                  <dd>{activeNode.ioContract.input}</dd>
                </div>
                <div>
                  <dt>Saída</dt>
                  <dd>{activeNode.ioContract.output}</dd>
                </div>
              </dl>
            </div>

            {/* Telemetria Langfuse limpa e tabular */}
            <div className="drawer-section">
              <div className="drawer-telemetry-header">
                <h3>Telemetria Langfuse</h3>
                <span className="langfuse-badge">
                  {activeNode.langfuse.isMock ? 'Mock Local' : 'Live Trace'}
                </span>
              </div>

              <div className="telemetry-list tabular-nums">
                <div className="telemetry-row">
                  <span className="telemetry-label">Trace ID</span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <code className="telemetry-code">{activeNode.langfuse.traceId}</code>
                    <button
                      type="button"
                      className="copy-btn"
                      onClick={() => copyTraceId(activeNode.langfuse.traceId)}
                      title="Copiar Trace ID"
                    >
                      {copiedTrace ? 'Copiado' : 'Copiar'}
                    </button>
                  </div>
                </div>

                <div className="telemetry-row">
                  <span className="telemetry-label">Span</span>
                  <code className="telemetry-code">{activeNode.langfuse.spanName}</code>
                </div>

                <div className="telemetry-row">
                  <span className="telemetry-label">Executor / Modelo</span>
                  <span className="telemetry-value-bold">{activeNode.modelName}</span>
                </div>

                <div className="telemetry-row">
                  <span className="telemetry-label">Tokens (In / Out)</span>
                  <span className="telemetry-value">
                    {activeNode.langfuse.tokensIn.toLocaleString('pt-BR')} /{' '}
                    {activeNode.langfuse.tokensOut.toLocaleString('pt-BR')}
                  </span>
                </div>

                <div className="telemetry-row">
                  <span className="telemetry-label">Custo da etapa</span>
                  <strong className="telemetry-value">{moneyUsd(activeNode.langfuse.costUsd)}</strong>
                </div>

                <div className="telemetry-row">
                  <span className="telemetry-label">Latência</span>
                  <span className="telemetry-value">{activeNode.langfuse.latencyMs} ms</span>
                </div>

                <div className="telemetry-row">
                  <span className="telemetry-label">Governança LGPD</span>
                  <span className="telemetry-lgpd-ok">PII mascarada antes do envio</span>
                </div>
              </div>

              <a
                href={`https://cloud.langfuse.com/project/smartrepair/traces/${activeNode.langfuse.traceId}`}
                target="_blank"
                rel="noreferrer"
                className="langfuse-action-btn"
              >
                Abrir Trace no Langfuse ↗
              </a>
            </div>

            {/* Ação principal contextual */}
            <div className="drawer-section">
              <div className="shortcuts-group">
                {activeNode.propertyId ? (
                  <>
                    <button
                      type="button"
                      className="shortcut-btn primary"
                      onClick={() => navigate(propertyUrl(activeNode.propertyId!, 'chat'))}
                    >
                      Abrir chat de {activeNode.label} →
                    </button>
                    <button
                      type="button"
                      className="shortcut-btn"
                      onClick={() => navigate(propertyUrl(activeNode.propertyId!, 'adm'))}
                    >
                      Revisar decisões do anfitrião
                    </button>
                  </>
                ) : (
                  <>
                    <button
                      type="button"
                      className="shortcut-btn primary"
                      onClick={() => navigate(propertyUrl('casa-aurora', 'adm'))}
                    >
                      Aprovar orçamento pendente (Casa Aurora) →
                    </button>
                    <button
                      type="button"
                      className="shortcut-btn"
                      onClick={() => navigate('/auditoria')}
                    >
                      Conferir orçamento e auditoria global
                    </button>
                  </>
                )}
              </div>
            </div>
          </div>
        </aside>
      </div>
    </div>
  )
}

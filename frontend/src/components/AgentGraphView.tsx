import { useState, useMemo } from 'react'
import type { Property } from '../contracts'
import { properties } from '../demo-data'
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
    statusLabel: '3 imóveis monitorados',
    summary: '1 chamado aguarda aprovação humana na Casa Aurora; 2 imóveis operam em triagem automática.',
    focusNodeId: 'node-3-adm',
    tone: 'waiting',
  },
  'city:Fortaleza': {
    statusLabel: 'Imóveis em Fortaleza (CE)',
    summary: 'Casa Aurora com aprovação pendente; Loft Jardim em operação regular.',
    focusNodeId: 'node-3-adm',
    tone: 'waiting',
  },
  'city:Recife': {
    statusLabel: 'Imóveis em Recife (PE)',
    summary: 'Studio Tech Porto Digital com atendimento comercial ativo no Nó 1.',
    focusNodeId: 'node-1',
    tone: 'success',
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

  const propList = useMemo(() => propertiesList.slice(0, 3), [propertiesList])

  const availableProperties = useMemo(() => {
    const list = propList.length > 0 ? propList : properties
    return list.map((p) => {
      let city = 'Brasil'
      if (p.location?.includes('Fortaleza')) city = 'Fortaleza'
      else if (p.location?.includes('Recife')) city = 'Recife'
      else if (p.location?.includes('Rio de Janeiro') || p.title?.includes('Copacabana')) city = 'Rio de Janeiro'
      else if (p.location?.includes('São Paulo') || p.title?.includes('Vila Madalena')) city = 'São Paulo'
      else if (p.location?.includes('Gramado') || p.title?.includes('Gramado')) city = 'Gramado'
      else if (p.location?.includes(',')) {
        const parts = p.location.split(',')
        city = parts[parts.length - 1]?.trim() || p.neighborhood || 'Brasil'
      } else if (p.neighborhood) {
        city = p.neighborhood
      }
      return {
        id: p.id,
        title: p.title,
        cityName: city,
      }
    })
  }, [propList])

  const availableCities = useMemo(() => {
    const set = new Set<string>()
    availableProperties.forEach((p) => {
      if (p.cityName) set.add(p.cityName)
    })
    set.add('Fortaleza')
    set.add('Recife')
    return Array.from(set)
  }, [availableProperties])

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
        y: 140,
        radius: 28,
        description:
          'Chamado elétrico em andamento (chuveiro). Orçamentos aguardam aprovação do anfitrião.',
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
        y: 285,
        radius: 28,
        description:
          'Loft urbano com reservas confirmadas e triagem de dúvidas ativas no Nó 1.',
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
        id: 'prop-portodigital',
        propertyId: 'prop-portodigital-04',
        label: 'Studio Tech',
        sublabel: 'Porto Digital · PE',
        type: 'property',
        x: 96,
        y: 430,
        radius: 28,
        description:
          'Studio no polo de inovação do Recife. Atendimento automático a dúvidas de check-in.',
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
          'Protege contra injection e direciona para atendimento comercial (Nó 1) ou manutenção (Nó 2).',
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
          'Job assíncrono que descobre e valida prestadores locais antes de gravar no banco.',
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
          'Conversa calorosa com potenciais hóspedes até a confirmação da reserva.',
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
          'Classifica categoria, urgência e cômodo do chamado em schema Pydantic v2.',
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
          'Consulta prestadores homologados e reúne orçamentos com controle de timeout.',
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
          'Apresenta comparativo ao anfitrião e pausa a execução até a aprovação explícita.',
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
          'Cruza urgência e calendário: urgente o quanto antes; normal prefere dias sem hóspede.',
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
          'Aguarda aceite do prestador. Se recusar, oferta automaticamente a próxima janela.',
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
          'Avisa hóspede se hospedado na data, registra na agenda e fecha o ticket.',
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

  const isCityFilter = selectedPropertyFilter.startsWith('city:')
  const selectedCity = isCityFilter ? selectedPropertyFilter.replace('city:', '') : ''

  function isNodeCityMatch(propertyId: string | undefined, city: string): boolean {
    if (!propertyId) return false
    if (city === 'Fortaleza') {
      return propertyId === 'casa-aurora' || propertyId === 'loft-jardim'
    }
    if (city === 'Recife') {
      return propertyId === 'prop-portodigital-04'
    }
    if (city === 'Rio de Janeiro') {
      return propertyId === 'prop-copacabana-01'
    }
    if (city === 'São Paulo') {
      return propertyId === 'prop-vilamadalena-02'
    }
    return false
  }

  function handleSelectPropertyFilter(filterId: string) {
    setSelectedPropertyFilter(filterId)
    const summary = PROPERTY_FLOW_SUMMARIES[filterId]
    if (summary) {
      setSelectedNodeId(summary.focusNodeId)
    } else if (filterId.startsWith('city:')) {
      const city = filterId.replace('city:', '')
      if (city === 'Fortaleza') setSelectedNodeId('node-3-adm')
      else setSelectedNodeId('node-1')
    }
  }

  const copyTraceId = (traceId: string) => {
    navigator.clipboard?.writeText(traceId)
    setCopiedTrace(true)
    setTimeout(() => setCopiedTrace(false), 2000)
  }

  return (
    <div className="agent-graph-page" aria-label="Visualização do Grafo de Agentes e Imóveis">
      {/* Cabeçalho minimalista */}
      <div className="agent-graph-header">
        <h1>Grafo de Fases dos Agentes & Imóveis</h1>
        <p className="agent-graph-lead">
          Selecione uma cidade ou imóvel para destacar sua rota operacional ou clique em qualquer etapa para inspecionar
          telemetria, custos e governança no <strong>Langfuse</strong>.
        </p>
      </div>

      {/* Layout Principal: Canvas + Inspetor Lateral */}
      <div className="graph-layout">
        <div className="graph-canvas-wrapper" aria-label="Canvas interativo do grafo">
          {/* Barra de ferramentas interna: Dropbox de Cidade / Imóvel + Legenda */}
          <div className="graph-card-toolbar">
            <div className="graph-filter-dropbox-wrap">
              <label htmlFor="graph-city-select" className="graph-filter-label">
                Cidade / Imóvel:
              </label>
              <div className="graph-select-shell">
                <select
                  id="graph-city-select"
                  className="graph-city-select"
                  value={selectedPropertyFilter}
                  onChange={(e) => handleSelectPropertyFilter(e.target.value)}
                  aria-label="Filtrar por Cidade ou Imóvel"
                >
                  <option value="all">Todas as Cidades e Imóveis</option>
                  {availableCities.length > 0 && (
                    <optgroup label="Filtrar por Cidade">
                      {availableCities.map((city) => (
                        <option key={`city-${city}`} value={`city:${city}`}>
                          📍 {city} (Todos os imóveis)
                        </option>
                      ))}
                    </optgroup>
                  )}
                  <optgroup label="Filtrar por Imóvel">
                    {availableProperties.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.title} ({p.cityName})
                      </option>
                    ))}
                  </optgroup>
                </select>
                <span className="select-chevron" aria-hidden="true">▾</span>
              </div>
            </div>

            <div className="graph-canvas-legend">
              <span>
                <i className="legend-dot prop-dot" /> Imóvel
              </span>
              <span>
                <i className="legend-dot router-dot" /> Concluído
              </span>
              <span>
                <i className="legend-dot resolver-dot" /> Aguardando ADM
              </span>
            </div>
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
                selectedPropertyFilter === 'all' ||
                (isCityFilter
                  ? (selectedCity === 'Fortaleza' && edge.activeFor.some((id) => ['all', 'casa-aurora', 'loft-jardim'].includes(id))) ||
                    (selectedCity === 'Recife' && edge.activeFor.some((id) => ['all', 'prop-portodigital-04'].includes(id)))
                  : edge.activeFor.includes(selectedPropertyFilter))

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
                (isCityFilter
                  ? isNodeCityMatch(node.propertyId, selectedCity)
                  : (node.propertyId && node.propertyId === selectedPropertyFilter)) ||
                (node.type !== 'property' &&
                  (selectedPropertyFilter === 'casa-aurora' || (isCityFilter && selectedCity === 'Fortaleza')
                    ? node.id !== 'node-1'
                    : selectedPropertyFilter === 'loft-jardim' ||
                        selectedPropertyFilter === 'prop-portodigital-04' ||
                        (isCityFilter && selectedCity === 'Recife')
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
            <div className="drawer-section">
              <p className="drawer-description">{activeNode.description}</p>
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

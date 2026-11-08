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

export function AgentGraphView({ navigate, propertiesList }: AgentGraphViewProps) {
  const [selectedPropertyFilter, setSelectedPropertyFilter] = useState<string>('all')
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>('node-3-adm')
  const [copiedTrace, setCopiedTrace] = useState(false)
  const [isGuideOpen, setIsGuideOpen] = useState(true)

  // Lista dos 4 imóveis base
  const propList = useMemo(() => {
    return propertiesList.slice(0, 4)
  }, [propertiesList])

  // Definição dos nós ("bolinhas") com suas coordenadas e metadados de observabilidade
  const nodes: AgentNode[] = useMemo(() => [
    // 1. Camada de Imóveis (X: 100)
    {
      id: 'prop-casa-aurora',
      propertyId: 'casa-aurora',
      label: 'Casa Aurora',
      sublabel: 'Praia do Futuro · CE',
      type: 'property',
      x: 100,
      y: 95,
      radius: 30,
      description: 'Imóvel com chamado elétrico ativo (chuveiro sem água quente). Ponto de origem das mensagens do hóspede e camareira.',
      modelName: 'Origem de Eventos / Chat',
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
      x: 100,
      y: 215,
      radius: 30,
      description: 'Imóvel urbano com manutenção preventiva de ar-condicionado em fila e reservas confirmadas.',
      modelName: 'Origem de Eventos / Chat',
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
      x: 100,
      y: 335,
      radius: 30,
      description: 'Refúgio à beira-mar com agenda de alta temporada e canal de atendimento disponível.',
      modelName: 'Origem de Eventos / Chat',
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
      x: 100,
      y: 455,
      radius: 30,
      description: 'Studio no polo de inovação do Recife com workstation e dúvidas frequentes sobre Wi-Fi e check-in inteligente.',
      modelName: 'Origem de Eventos / Chat',
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

    // 2. Camada de Entrada & Roteamento (X: 275)
    {
      id: 'node-router',
      label: 'Roteador',
      sublabel: 'Guardrail + 4B',
      type: 'router',
      x: 275,
      y: 275,
      radius: 34,
      phaseNumber: 'R',
      description: 'Ponto único de entrada por imóvel. Aplica guardrails de injeção de prompt e classifica a intenção entre dúvida comercial (Nó 1) ou manutenção (Nó 2).',
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

    // 3. Nó S: Coletor de Prestadores (Job APScheduler) (X: 275, Y: 95)
    {
      id: 'node-s',
      label: 'Nó S: Coletor',
      sublabel: 'APScheduler (Cron)',
      type: 'collector',
      x: 275,
      y: 95,
      radius: 28,
      phaseNumber: 'S',
      description: 'Job periódico e assíncrono que coleta prestadores (Google Places / fixture), envia mensagens de validação e salva no PostgreSQL apenas os confirmados.',
      modelName: 'APScheduler + Qwen3.5-4B',
      defaultStatus: 'idle',
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

    // 4. Camada de Agentes de Triagem (X: 450)
    {
      id: 'node-1',
      label: 'Nó 1: Comercial',
      sublabel: 'Atendimento & Reserva',
      type: 'commercial',
      x: 450,
      y: 190,
      radius: 32,
      phaseNumber: '1',
      description: 'Conversa de forma calorosa com o potencial hóspede, tira dúvidas sobre amenidades e regras do imóvel até fechar a reserva ("temos inquilino").',
      modelName: 'Qwen/Qwen3.5-9B (Featherless)',
      defaultStatus: 'idle',
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
      sublabel: 'Classificação Pydantic',
      type: 'validator',
      x: 450,
      y: 360,
      radius: 32,
      phaseNumber: '2',
      description: 'Recebe relatos de inquilinos ou camareiras, faz perguntas de esclarecimento e gera tickets estruturados com categoria, urgência e cômodo.',
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

    // 5. Camada Nó 3: LangGraph Resolvedor (X: 620 a 960)
    {
      id: 'node-3-quotes',
      label: '3.1 Cotações',
      sublabel: 'Coleta com Timeout',
      type: 'resolver',
      x: 620,
      y: 360,
      radius: 28,
      phaseNumber: '3.1',
      description: 'Consulta prestadores homologados no PostgreSQL e dispara pedidos de orçamento simultâneos com controle rigoroso de timeout de 60 min.',
      modelName: 'LangGraph + Template Engine',
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
      sublabel: 'Interrupt Humano',
      type: 'resolver',
      x: 620,
      y: 470,
      radius: 34,
      phaseNumber: '3.2',
      description: 'Apresenta a síntese comparativa dos orçamentos ao anfitrião e pausa a execução (interrupt do LangGraph) aguardando aprovação explícita.',
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
      x: 790,
      y: 470,
      radius: 28,
      phaseNumber: '3.3',
      description: 'Aplica a regra determinística cruzando urgência do chamado e agenda do imóvel: urgente é o quanto antes; normal prefere dias sem hóspede.',
      modelName: 'Regra Determinística (Sem LLM)',
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
      sublabel: 'Aceite / Recusa do Dia',
      type: 'resolver',
      x: 790,
      y: 360,
      radius: 28,
      phaseNumber: '3.4',
      description: 'Aguarda confirmação do prestador sobre a data proposta. Em caso de recusa, retorna automaticamente ao cálculo de nova janela (passo 3.3).',
      modelName: 'Qwen/Qwen3.5-4B Guardrail',
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
      sublabel: 'Aviso ao Hóspede',
      type: 'resolver',
      x: 960,
      y: 360,
      radius: 30,
      phaseNumber: '3.5',
      description: 'Se houver hóspede na data marcada, envia mensagem cordial com horário de chegada do profissional, grava na agenda e fecha o ticket.',
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
  ], [])

  // Conexões direcionadas entre os nós
  const edges = useMemo(() => [
    // Imóveis para Roteador
    { from: 'prop-casa-aurora', to: 'node-router', label: 'Mensagens', activeFor: ['all', 'casa-aurora'] },
    { from: 'prop-loft-jardim', to: 'node-router', label: 'Mensagens', activeFor: ['all', 'loft-jardim'] },
    { from: 'prop-vila-areia', to: 'node-router', label: 'Mensagens', activeFor: ['all', 'vila-areia'] },
    { from: 'prop-portodigital', to: 'node-router', label: 'Mensagens', activeFor: ['all', 'prop-portodigital-04'] },

    // Roteador para Nó 1 e Nó 2
    { from: 'node-router', to: 'node-1', label: 'Dúvidas / Reservas (Fluxo A)', activeFor: ['all', 'loft-jardim', 'prop-portodigital-04'] },
    { from: 'node-router', to: 'node-2', label: 'Manutenção (Fluxo C)', activeFor: ['all', 'casa-aurora'] },

    // Nó S alimenta Nó 3.1
    { from: 'node-s', to: 'node-3-quotes', label: 'Base de Prestadores (Fluxo B)', dashed: true, activeFor: ['all', 'casa-aurora'] },

    // Nó 2 para Nó 3.1
    { from: 'node-2', to: 'node-3-quotes', label: 'Ticket Aberto', activeFor: ['all', 'casa-aurora'] },

    // Ciclo LangGraph Nó 3
    { from: 'node-3-quotes', to: 'node-3-adm', label: 'Orçamentos Coletados', activeFor: ['all', 'casa-aurora'] },
    { from: 'node-3-adm', to: 'node-3-schedule', label: 'Escolha Aprovada', activeFor: ['all', 'casa-aurora'] },
    { from: 'node-3-schedule', to: 'node-3-confirm', label: 'Data Proposta', activeFor: ['all', 'casa-aurora'] },
    { from: 'node-3-confirm', to: 'node-3-schedule', label: 'Recusa (Loop)', curveBack: true, dashed: true, activeFor: ['all'] },
    { from: 'node-3-confirm', to: 'node-3-notify', label: 'Data Aceita', activeFor: ['all', 'casa-aurora'] },
  ], [])

  // Nó atualmente selecionado para o Drawer
  const activeNode = useMemo(() => {
    return nodes.find((n) => n.id === selectedNodeId) ?? nodes[0]!
  }, [nodes, selectedNodeId])

  const copyTraceId = (traceId: string) => {
    navigator.clipboard?.writeText(traceId)
    setCopiedTrace(true)
    setTimeout(() => setCopiedTrace(false), 2000)
  }

  return (
    <div className="agent-graph-page" aria-label="Visualização do Grafo de Agentes e Imóveis">
      {/* Cabeçalho da página */}
      <div className="agent-graph-header">
        <div>
          <span className="eyebrow">ARQUITETURA DE AGENTES · MULTI-IMÓVEL</span>
          <h1 style={{ margin: '4px 0 8px' }}>Grafo de Fases dos Agentes & Imóveis</h1>
          <p style={{ margin: 0, color: 'var(--mar-72)', maxWidth: '780px' }}>
            Visão ponta a ponta dos três fluxos independentes (Aquisição, Coleta de Prestadores e Manutenção via LangGraph),
            integrada à observabilidade completa e telemetria de custos do <strong>Langfuse</strong>.
          </p>
        </div>

        {/* Filtro por Imóvel */}
        <div className="graph-filter-container">
          <span className="filter-label">Filtrar por Imóvel:</span>
          <div className="filter-pill-group" role="radiogroup" aria-label="Filtrar imóvel no grafo">
            <button
              type="button"
              className={`filter-pill ${selectedPropertyFilter === 'all' ? 'active' : ''}`}
              onClick={() => setSelectedPropertyFilter('all')}
            >
              Todos os Imóveis
            </button>
            {propList.map((p) => (
              <button
                key={p.id}
                type="button"
                className={`filter-pill ${selectedPropertyFilter === p.id ? 'active' : ''}`}
                onClick={() => setSelectedPropertyFilter(p.id)}
              >
                {p.title}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Accordion do Guia Langfuse */}
      <section className="langfuse-guide-card">
        <header
          className="langfuse-guide-header"
          onClick={() => setIsGuideOpen((prev) => !prev)}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') setIsGuideOpen((p) => !p) }}
          aria-expanded={isGuideOpen}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span className="langfuse-sparkle">✦</span>
            <div>
              <strong>Como funciona a Observabilidade com Langfuse nesta aplicação?</strong>
              <small style={{ display: 'block', color: 'var(--mar-72)' }}>
                Rastreamento de Traces, Spans, contagem de tokens, custos reais e governança LGPD
              </small>
            </div>
          </div>
          <span className="guide-chevron">{isGuideOpen ? '▲ Recolher' : '▼ Expandir Guia'}</span>
        </header>

        {isGuideOpen && (
          <div className="langfuse-guide-body">
            <div className="langfuse-grid-cols">
              <div className="langfuse-step-box">
                <span className="step-tag">1. Traces & Spans</span>
                <h4>Ciclo por Imóvel</h4>
                <p>
                  Cada relato ou conversa no imóvel gera um <code>Trace</code> (identificado pelo <code>run_id</code>). Cada agente
                  (Roteador, Nó 1, Nó 2, Nó 3) roda dentro de um <code>Span</code> filho rastreando latência e dependências.
                </p>
              </div>

              <div className="langfuse-step-box">
                <span className="step-tag">2. Mascaramento LGPD</span>
                <h4>Proteção de PII</h4>
                <p>
                  Antes de qualquer dado ser transmitido, o wrapper em <code>backend/app/observability/langfuse_client.py</code>
                  mascara CPFs, chaves Pix, telefones e e-mails com regex determinística.
                </p>
              </div>

              <div className="langfuse-step-box">
                <span className="step-tag">3. Custo Explícito</span>
                <h4>Preços Featherless</h4>
                <p>
                  O custo em USD de cada geração é computado com precisão e injetado nos metadados do Langfuse (ex: 
                  Qwen3.5-4B a US$ 0,10/1M in e US$ 0,20/1M out; Qwen3.5-9B a US$ 0,17/1M in e US$ 0,25/1M out).
                </p>
              </div>

              <div className="langfuse-step-box">
                <span className="step-tag">4. Ativação Rápida</span>
                <h4>Credenciais no .env</h4>
                <p>
                  Configure <code>LANGFUSE_PUBLIC_KEY</code>, <code>LANGFUSE_SECRET_KEY</code> e <code>LANGFUSE_HOST</code> no 
                  <code>backend/.env</code>. Em caso de ausência de chaves, o modo mock local mantém o sistema 100% funcional.
                </p>
              </div>
            </div>
          </div>
        )}
      </section>

      {/* Conteúdo Principal: Canvas do Grafo + Drawer Lateral */}
      <div className="graph-layout">
        {/* Canvas Interativo do Grafo */}
        <div className="graph-canvas-wrapper" aria-label="Canvas interativo do grafo">
          <div className="graph-canvas-legend">
            <span><i className="legend-dot prop-dot" /> Imóveis Cadastrados</span>
            <span><i className="legend-dot router-dot" /> Roteador de Entrada</span>
            <span><i className="legend-dot commercial-dot" /> Nó 1: Comercial</span>
            <span><i className="legend-dot collector-dot" /> Nó S: Coletor Prestadores</span>
            <span><i className="legend-dot validator-dot" /> Nó 2: Validador</span>
            <span><i className="legend-dot resolver-dot" /> Nó 3: LangGraph Resolvedor</span>
          </div>

          <svg viewBox="0 0 1060 560" className="agent-graph-svg" role="img" aria-label="Diagrama do Grafo dos Agentes">
            <defs>
              {/* Marcador de seta normal */}
              <marker id="arrow" viewBox="0 0 10 10" refX="24" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#17323A" opacity="0.6" />
              </marker>

              {/* Marcador de seta ativa em âmbar */}
              <marker id="arrow-active" viewBox="0 0 10 10" refX="24" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#F2A541" />
              </marker>

              {/* Filtro de sombra suave */}
              <filter id="node-shadow" x="-20%" y="-20%" width="140%" height="140%">
                <feDropShadow dx="0" dy="4" stdDeviation="4" floodColor="#17323A" floodOpacity="0.12" />
              </filter>
            </defs>

            {/* Linhas de conexão (Edges) */}
            {edges.map((edge, idx) => {
              const sourceNode = nodes.find((n) => n.id === edge.from)
              const targetNode = nodes.find((n) => n.id === edge.to)
              if (!sourceNode || !targetNode) return null

              const isEdgeActive =
                selectedPropertyFilter === 'all' ||
                edge.activeFor.includes(selectedPropertyFilter)

              // Coordenadas das curvas de Bezier
              const dx = targetNode.x - sourceNode.x

              let pathD: string
              if (edge.curveBack) {
                // Loop de retorno de recusa (3.4 -> 3.3)
                pathD = `M ${sourceNode.x} ${sourceNode.y} C ${sourceNode.x + 30} ${sourceNode.y + 60}, ${targetNode.x + 30} ${targetNode.y - 60}, ${targetNode.x} ${targetNode.y}`
              } else {
                const cx1 = sourceNode.x + dx * 0.5
                const cy1 = sourceNode.y
                const cx2 = sourceNode.x + dx * 0.5
                const cy2 = targetNode.y
                pathD = `M ${sourceNode.x} ${sourceNode.y} C ${cx1} ${cy1}, ${cx2} ${cy2}, ${targetNode.x} ${targetNode.y}`
              }

              return (
                <g key={`edge-${idx}`} className={`graph-edge ${isEdgeActive ? 'active' : 'dimmed'}`}>
                  <path
                    d={pathD}
                    fill="none"
                    stroke={isEdgeActive ? '#F2A541' : 'rgba(23, 50, 58, 0.22)'}
                    strokeWidth={isEdgeActive ? 2.5 : 1.5}
                    strokeDasharray={edge.dashed ? '5,5' : undefined}
                    markerEnd={isEdgeActive ? 'url(#arrow-active)' : 'url(#arrow)'}
                  />
                </g>
              )
            })}

            {/* Nós circulares ("bolinhas") */}
            {nodes.map((node) => {
              const isSelected = selectedNodeId === node.id
              const isPropertyMatch =
                selectedPropertyFilter === 'all' ||
                (node.propertyId && node.propertyId === selectedPropertyFilter) ||
                (node.type !== 'property' && ['all', 'casa-aurora'].includes(selectedPropertyFilter))

              const isPulsing = node.defaultStatus === 'waiting' && isPropertyMatch

              // Cores do nó por tipo
              let strokeColor = '#17323A'
              let fillColor = '#FFFFFF'
              const labelColor = '#17323A'

              if (node.type === 'property') {
                fillColor = '#F6F3EE'
                strokeColor = '#17323A'
              } else if (node.type === 'router') {
                strokeColor = '#17323A'
                fillColor = '#FFFFFF'
              } else if (node.type === 'resolver' && node.id === 'node-3-adm') {
                strokeColor = '#F2A541'
                fillColor = '#FFFBF5'
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
                  onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') setSelectedNodeId(node.id) }}
                >
                  {/* Halo pulsante para estados aguardando / em execução */}
                  {isPulsing && (
                    <circle
                      cx={node.x}
                      cy={node.y}
                      r={node.radius + 10}
                      fill="none"
                      stroke="#F2A541"
                      strokeWidth="2"
                      opacity="0.6"
                      className="pulse-halo"
                    />
                  )}

                  {/* Círculo base da bolinha */}
                  <circle
                    cx={node.x}
                    cy={node.y}
                    r={node.radius}
                    fill={fillColor}
                    stroke={strokeColor}
                    strokeWidth={isSelected ? 3.5 : 2}
                    filter="url(#node-shadow)"
                    className="node-circle"
                  />

                  {/* Número ou identificador da fase dentro da bolinha */}
                  {node.phaseNumber && (
                    <text
                      x={node.x}
                      y={node.y + 5}
                      textAnchor="middle"
                      fill={strokeColor}
                      fontSize="13"
                      fontWeight="700"
                      fontFamily="Plus Jakarta Sans, sans-serif"
                    >
                      {node.phaseNumber}
                    </text>
                  )}

                  {/* Ícone sutil para imóveis */}
                  {node.type === 'property' && (
                    <text
                      x={node.x}
                      y={node.y + 5}
                      textAnchor="middle"
                      fill="#17323A"
                      fontSize="14"
                    >
                      🏠
                    </text>
                  )}

                  {/* Rótulo superior / inferior da bolinha */}
                  <text
                    x={node.x}
                    y={node.y + node.radius + 16}
                    textAnchor="middle"
                    fill={labelColor}
                    fontSize="12"
                    fontWeight="600"
                    fontFamily="Inter, sans-serif"
                  >
                    {node.label}
                  </text>

                  <text
                    x={node.x}
                    y={node.y + node.radius + 28}
                    textAnchor="middle"
                    fill="rgba(23, 50, 58, 0.65)"
                    fontSize="10"
                    fontFamily="Inter, sans-serif"
                  >
                    {node.sublabel}
                  </text>
                </g>
              )
            })}
          </svg>
        </div>

        {/* Drawer Lateral com Detalhes e Telemetria Langfuse */}
        <aside className="graph-drawer" aria-label="Detalhes do nó selecionado e telemetria">
          <div className="drawer-header">
            <div>
              <span className="node-type-badge">{activeNode.type.toUpperCase()}</span>
              <h2 style={{ margin: '4px 0 2px', fontSize: '18px' }}>{activeNode.label}</h2>
              <span style={{ fontSize: '12px', color: 'var(--mar-72)' }}>{activeNode.sublabel}</span>
            </div>
            <button
              type="button"
              className="drawer-close-btn"
              onClick={() => setSelectedNodeId(null)}
              aria-label="Fechar painel de detalhes"
            >
              ✕
            </button>
          </div>

          <div className="drawer-content">
            {/* Status do nó */}
            <div className="drawer-section">
              <span className="drawer-section-title">ESTADO DO PIPELINE</span>
              <div className="node-status-card">
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span
                    className={`status-indicator ${
                      activeNode.defaultStatus === 'waiting'
                        ? 'indicator-waiting'
                        : activeNode.defaultStatus === 'success'
                        ? 'indicator-success'
                        : 'indicator-idle'
                    }`}
                  />
                  <strong>
                    {activeNode.defaultStatus === 'waiting'
                      ? 'Aguardando Decisão Humana (Interrupt)'
                      : activeNode.defaultStatus === 'success'
                      ? 'Processado com Sucesso'
                      : 'Pronto / Ocioso'}
                  </strong>
                </div>
                <p style={{ margin: '8px 0 0', fontSize: '13px', color: 'var(--mar-72)' }}>
                  {activeNode.description}
                </p>
              </div>
            </div>

            {/* Cartão de Telemetria Langfuse */}
            <div className="drawer-section">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span className="drawer-section-title">OBSERVABILIDADE LANGFUSE</span>
                <span className="langfuse-badge">
                  {activeNode.langfuse.isMock ? 'MODO OFFLINE / MOCK' : 'LIVE TELEMETRY'}
                </span>
              </div>

              <div className="telemetry-card">
                {/* Trace ID */}
                <div className="telemetry-row">
                  <span className="telemetry-label">Trace ID (run_id):</span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <code className="telemetry-code">{activeNode.langfuse.traceId}</code>
                    <button
                      type="button"
                      className="copy-btn"
                      onClick={() => copyTraceId(activeNode.langfuse.traceId)}
                      title="Copiar Trace ID"
                    >
                      {copiedTrace ? '✓' : '⧉'}
                    </button>
                  </div>
                </div>

                {/* Span */}
                <div className="telemetry-row">
                  <span className="telemetry-label">Span / Agente:</span>
                  <span className="telemetry-value">{activeNode.langfuse.spanName}</span>
                </div>

                {/* Modelo LLM */}
                <div className="telemetry-row">
                  <span className="telemetry-label">Modelo LLM:</span>
                  <span className="telemetry-value-bold">{activeNode.modelName}</span>
                </div>

                {/* Grid de Métricas */}
                <div className="telemetry-metrics-grid">
                  <div className="metric-box">
                    <span className="metric-box-label">Tokens Entrada</span>
                    <strong>{activeNode.langfuse.tokensIn.toLocaleString('pt-BR')}</strong>
                  </div>
                  <div className="metric-box">
                    <span className="metric-box-label">Tokens Saída</span>
                    <strong>{activeNode.langfuse.tokensOut.toLocaleString('pt-BR')}</strong>
                  </div>
                  <div className="metric-box">
                    <span className="metric-box-label">Custo Estimado</span>
                    <strong style={{ color: '#17323A' }}>{moneyUsd(activeNode.langfuse.costUsd)}</strong>
                  </div>
                  <div className="metric-box">
                    <span className="metric-box-label">Latência</span>
                    <strong>{activeNode.langfuse.latencyMs} ms</strong>
                  </div>
                </div>

                {/* Selo LGPD */}
                <div className="lgpd-protection-badge">
                  <span>🔒 Mascaramento LGPD: <strong>Ativo</strong> (CPFs, e-mails e contatos sanitizados)</span>
                </div>

                {/* Botão de ação Langfuse */}
                <a
                  href={`https://cloud.langfuse.com/project/smartrepair/traces/${activeNode.langfuse.traceId}`}
                  target="_blank"
                  rel="noreferrer"
                  className="langfuse-action-btn"
                >
                  Visualizar Trace no Langfuse ↗
                </a>
              </div>
            </div>

            {/* Atalhos Rápidos */}
            <div className="drawer-section">
              <span className="drawer-section-title">ATALHOS DO IMÓVEL</span>
              <div className="shortcuts-group">
                {activeNode.propertyId ? (
                  <>
                    <button
                      type="button"
                      className="shortcut-btn primary"
                      onClick={() => navigate(propertyUrl(activeNode.propertyId!, 'chat'))}
                    >
                      Abrir Chat do Imóvel ↗
                    </button>
                    <button
                      type="button"
                      className="shortcut-btn"
                      onClick={() => navigate(propertyUrl(activeNode.propertyId!, 'adm'))}
                    >
                      Ir para Sessão Agente ⇄ Anfitrião
                    </button>
                  </>
                ) : (
                  <>
                    <button
                      type="button"
                      className="shortcut-btn primary"
                      onClick={() => navigate(propertyUrl('casa-aurora', 'adm'))}
                    >
                      Ver Decisão Pendente (Casa Aurora) ↗
                    </button>
                    <button
                      type="button"
                      className="shortcut-btn"
                      onClick={() => navigate('/auditoria')}
                    >
                      Ver Auditoria & Custos Gerais
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

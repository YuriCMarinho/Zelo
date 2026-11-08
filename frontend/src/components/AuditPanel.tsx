import { useEffect, useState } from 'react'
import { fetchAuditEvents, fetchCostSummary } from '../api/client'
import type { AuditEvent, CostSummary } from '../contracts'

const usd = (val: number | undefined) =>
  new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'USD', minimumFractionDigits: 4 }).format(val ?? 0)

export function AuditPanel() {
  const [costs, setCosts] = useState<CostSummary | null>(null)
  const [events, setEvents] = useState<AuditEvent[]>([])
  const [loading, setLoading] = useState(false)

  async function loadData() {
    setLoading(true)
    try {
      const [c, e] = await Promise.all([fetchCostSummary(), fetchAuditEvents()])
      setCosts(c)
      setEvents(e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    let ignore = false
    Promise.all([fetchCostSummary(), fetchAuditEvents()]).then(([c, e]) => {
      if (!ignore) {
        setCosts(c)
        setEvents(e)
      }
    })
    return () => {
      ignore = true
    }
  }, [])

  const budgetLimit = costs?.budget_limit_usd ?? 25
  const percentage = costs?.percentage_used ?? 0

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Resumo de Consumo de Orçamento */}
      <section className="timeline-card" style={{ padding: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
          <div>
            <h2 style={{ margin: 0, fontSize: '20px', letterSpacing: '-0.02em' }}>Consumo do Orçamento Featherless</h2>
            <span style={{ fontSize: '13px', color: 'var(--mar-72)' }}>
              Teto global: US$ {budgetLimit.toFixed(2)} · Telemetria em tempo real
            </span>
          </div>
          <button
            type="button"
            className="card-btn"
            style={{ background: 'var(--mar-08)', color: 'var(--mar-profundo)', padding: '8px 16px', borderRadius: '10px' }}
            onClick={loadData}
            disabled={loading}
          >
            {loading ? 'Atualizando...' : 'Atualizar'}
          </button>
        </div>

        {/* Barra de Progresso do Orçamento */}
        <div style={{ marginBottom: '24px' }}>
          <div
            style={{
              height: '8px',
              width: '100%',
              background: 'var(--mar-08)',
              borderRadius: '999px',
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                height: '100%',
                width: `${Math.min(Math.max(percentage, 1), 100)}%`,
                background: percentage > 70 ? '#D9534F' : 'var(--ambar)',
                borderRadius: '999px',
                transition: 'width 0.4s ease',
              }}
            />
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '14px' }}>
          <div style={{ padding: '16px', background: 'var(--areia)', borderRadius: '12px' }}>
            <span style={{ fontSize: '12px', color: 'var(--mar-72)' }}>Gasto Total</span>
            <div style={{ fontSize: '22px', fontWeight: 700, marginTop: '2px' }} className="tabular-nums">
              {usd(costs?.total_cost_usd)}
            </div>
            <span style={{ fontSize: '11.5px', color: 'var(--mar-72)' }}>
              Saldo restante: {usd(budgetLimit - (costs?.total_cost_usd ?? 0))}
            </span>
          </div>

          <div style={{ padding: '16px', background: 'var(--areia)', borderRadius: '12px' }}>
            <span style={{ fontSize: '12px', color: 'var(--mar-72)' }}>Chamadas LLM</span>
            <div style={{ fontSize: '22px', fontWeight: 700, marginTop: '2px' }} className="tabular-nums">
              {costs?.total_calls ?? 0}
            </div>
            <span style={{ fontSize: '11.5px', color: 'var(--mar-72)' }} className="tabular-nums">
              {costs?.total_input_tokens?.toLocaleString('pt-BR') ?? 0} in · {costs?.total_output_tokens?.toLocaleString('pt-BR') ?? 0} out
            </span>
          </div>

          <div style={{ padding: '16px', background: 'var(--areia)', borderRadius: '12px' }}>
            <span style={{ fontSize: '12px', color: 'var(--mar-72)' }}>Uso da Cota</span>
            <div style={{ fontSize: '22px', fontWeight: 700, marginTop: '2px' }} className="tabular-nums">
              {percentage.toFixed(2)}%
            </div>
            <span style={{ fontSize: '11.5px', color: 'var(--mar-72)' }}>
              Limite seguro mantido
            </span>
          </div>
        </div>

        {/* Detalhamento por Nó minimalista */}
        {costs?.by_node && Object.keys(costs.by_node).length > 0 && (
          <div style={{ marginTop: '20px', paddingTop: '16px', borderTop: '1px solid var(--mar-08)' }}>
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              {Object.entries(costs.by_node).map(([node, cost]) => (
                <span
                  key={node}
                  className="tabular-nums"
                  style={{
                    padding: '5px 12px',
                    borderRadius: '8px',
                    background: 'var(--areia)',
                    border: '1px solid var(--mar-16)',
                    fontSize: '12px',
                    color: 'var(--mar-profundo)',
                  }}
                >
                  <strong style={{ fontWeight: 600 }}>{node}:</strong> {usd(cost)}
                </span>
              ))}
            </div>
          </div>
        )}
      </section>

      {/* Trilha de Eventos Minimalista */}
      <section className="timeline-card" style={{ padding: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <h3 style={{ margin: 0, fontSize: '18px', letterSpacing: '-0.02em' }}>Eventos Recentes</h3>
          <span className="tabular-nums" style={{ fontSize: '12px', color: 'var(--mar-72)' }}>
            {events.length} registrado(s)
          </span>
        </div>

        <div className="audit-list">
          {events.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '32px 16px', color: 'var(--mar-72)', fontSize: '13px' }}>
              Nenhum evento registrado ainda. As mensagens e aprovações aparecerão aqui.
            </div>
          ) : (
            events.map((ev) => (
              <div
                key={ev.id}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '12px 14px',
                  background: 'var(--areia)',
                  borderRadius: '10px',
                  border: '1px solid var(--mar-08)',
                  fontSize: '13px',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <span
                    style={{
                      fontSize: '11px',
                      fontWeight: 700,
                      padding: '3px 8px',
                      borderRadius: '6px',
                      background: 'var(--branco)',
                      border: '1px solid var(--mar-16)',
                      color: 'var(--mar-profundo)',
                    }}
                  >
                    {ev.node}
                  </span>
                  <strong>{ev.event_type}</strong>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '12px', color: 'var(--mar-72)', fontSize: '12px' }} className="tabular-nums">
                  {ev.ticket_id && (
                    <span style={{ fontFamily: 'monospace', fontSize: '11px' }}>
                      #{ev.ticket_id.slice(0, 8)}
                    </span>
                  )}
                  <time>{new Date(ev.created_at).toLocaleTimeString('pt-BR')}</time>
                </div>
              </div>
            ))
          )}
        </div>
      </section>
    </div>
  )
}

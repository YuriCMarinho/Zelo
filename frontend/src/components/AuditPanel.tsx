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

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '28px' }}>
      {/* Bloco de Orçamento e Custos */}
      <section className="timeline-card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <span className="eyebrow">AUDITORIA DE CUSTOS · LEDGER REAL</span>
            <h2 style={{ margin: '4px 0 0', fontSize: '24px' }}>Consumo do Orçamento Featherless</h2>
          </div>
          <button
            type="button"
            className="card-btn"
            style={{ background: 'var(--mar-08)', color: 'var(--mar-profundo)' }}
            onClick={loadData}
            disabled={loading}
          >
            {loading ? 'Atualizando...' : 'Atualizar Dados'}
          </button>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
          <div style={{ padding: '16px', background: 'var(--areia)', borderRadius: '14px' }}>
            <span style={{ fontSize: '12px', color: 'var(--mar-72)' }}>Total Gasto (US$)</span>
            <div style={{ fontSize: '24px', fontWeight: 800, marginTop: '4px' }} className="tabular-nums">
              {usd(costs?.total_cost_usd)}
            </div>
            <span style={{ fontSize: '11px', color: 'var(--mar-72)' }}>
              Teto global: US$ {costs?.budget_limit_usd?.toFixed(2) ?? '25.00'}
            </span>
          </div>

          <div style={{ padding: '16px', background: 'var(--areia)', borderRadius: '14px' }}>
            <span style={{ fontSize: '12px', color: 'var(--mar-72)' }}>Chamadas de Inferência</span>
            <div style={{ fontSize: '24px', fontWeight: 800, marginTop: '4px' }} className="tabular-nums">
              {costs?.total_calls ?? 0}
            </div>
            <span style={{ fontSize: '11px', color: 'var(--mar-72)' }}>
              {costs?.total_input_tokens ?? 0} in · {costs?.total_output_tokens ?? 0} out tokens
            </span>
          </div>

          <div style={{ padding: '16px', background: 'var(--areia)', borderRadius: '14px' }}>
            <span style={{ fontSize: '12px', color: 'var(--mar-72)' }}>Uso do Limite Global</span>
            <div style={{ fontSize: '24px', fontWeight: 800, marginTop: '4px', color: 'var(--mar-profundo)' }}>
              {costs?.percentage_used?.toFixed(2) ?? '0.00'}%
            </div>
            <span style={{ fontSize: '11px', color: 'var(--mar-72)' }}>
              Reserva de 30% garantida para S3
            </span>
          </div>
        </div>

        {/* Detalhamento por Nó */}
        {costs?.by_node && Object.keys(costs.by_node).length > 0 && (
          <div>
            <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--mar-72)' }}>
              DISTRIBUIÇÃO DE CUSTO POR NÓ (US$)
            </span>
            <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', marginTop: '8px' }}>
              {Object.entries(costs.by_node).map(([node, cost]) => (
                <span
                  key={node}
                  style={{
                    padding: '6px 12px',
                    borderRadius: '8px',
                    background: 'var(--mar-08)',
                    fontSize: '12px',
                    fontWeight: 600,
                  }}
                >
                  {node}: {usd(cost)}
                </span>
              ))}
            </div>
          </div>
        )}
      </section>

      {/* Trilha de Auditoria */}
      <section className="timeline-card">
        <div>
          <span className="eyebrow">RASTREABILIDADE COMPLETA · LGPD COMPLIANT</span>
          <h2 style={{ margin: '4px 0 0', fontSize: '24px' }}>Eventos de Auditoria Recentes</h2>
          <p style={{ margin: '4px 0 16px', fontSize: '13px', color: 'var(--mar-72)' }}>
            Todos os eventos de recebimento de mensagem, criação de chamado, cotação e aprovação do ADM.
          </p>
        </div>

        <div className="audit-list">
          {events.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '24px', color: 'var(--mar-72)', fontSize: '13px' }}>
              Nenhum evento registrado ainda. Envie uma mensagem pelo chat ou use o simulador para gerar ações.
            </div>
          ) : (
            events.map((ev) => (
              <div key={ev.id} className="audit-item" style={{ flexDirection: 'column', alignItems: 'stretch' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span className="audit-node">{ev.node}</span>
                    <strong>{ev.event_type}</strong>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '14px', fontSize: '11px', color: 'var(--mar-72)' }}>
                    <span>{ev.ticket_id ? `#${ev.ticket_id.slice(0, 8)}` : ev.run_id.slice(0, 12)}</span>
                    <time>{new Date(ev.created_at).toLocaleTimeString('pt-BR')}</time>
                  </div>
                </div>
                {ev.payload && Object.keys(ev.payload).length > 0 && (
                  <details style={{ marginTop: '6px', fontSize: '12px' }}>
                    <summary style={{ cursor: 'pointer', color: 'var(--mar-profundo)', fontWeight: 600 }}>
                      Ver dados da operação ({Object.keys(ev.payload).join(', ')})
                    </summary>
                    <pre style={{ margin: '6px 0 0', padding: '8px 12px', background: 'var(--areia)', borderRadius: '8px', fontSize: '11px', overflowX: 'auto', border: '1px solid var(--mar-08)' }}>
                      {JSON.stringify(ev.payload, null, 2)}
                    </pre>
                  </details>
                )}
              </div>
            ))
          )}
        </div>
      </section>
    </div>
  )
}

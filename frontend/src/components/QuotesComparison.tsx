import { useEffect, useState } from 'react'
import { fetchAuditEvents } from '../api/client'
import type { AuditEvent, MaintenanceTicket, Property, Quote } from '../contracts'

const money = (val: number | null | undefined) =>
  val != null
    ? new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 }).format(val)
    : 'A combinar'

interface QuotesComparisonProps {
  property: Property
  ticket: MaintenanceTicket | null
  quotes: Quote[]
  onApprove: (providerId: string) => Promise<void>
  onBack?: () => void
  isLoading?: boolean
}

export function QuotesComparison({
  property,
  ticket,
  quotes,
  onApprove,
  onBack,
  isLoading = false,
}: QuotesComparisonProps) {
  const [selectedProviderId, setSelectedProviderId] = useState<string | null>(() => {
    if (ticket?.selected_provider_id) return ticket.selected_provider_id
    // Seleciona por padrão o primeiro ou o recomendado
    const recommended = quotes.find((q) => q.is_recommended)
    return recommended ? recommended.provider_id : quotes[0]?.provider_id || null
  })
  const [submitting, setSubmitting] = useState(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([])

  useEffect(() => {
    let ignore = false
    if (!ticket?.id) return

    fetchAuditEvents(ticket.id)
      .then((evs) => {
        if (!ignore) {
          setAuditEvents(evs)
        }
      })
      .catch(() => {
        // Ignora erro em modo demo/mock
      })

    return () => {
      ignore = true
    }
  }, [ticket?.id, ticket?.status])

  const selectedQuote = quotes.find((q) => q.provider_id === selectedProviderId) || quotes[0]

  const statusLabel = () => {
    if (!ticket) return 'Nenhum chamado aberto'
    switch (ticket.status) {
      case 'awaiting_adm_approval':
        return 'Aguardando sua decisão'
      case 'waiting_quotes':
        return 'Buscando orçamentos'
      case 'scheduling':
      case 'waiting_date_confirmation':
      case 'proposing_date':
        return 'Confirmando com prestador'
      case 'confirmed_schedule':
      case 'resolved':
        return ticket.scheduled_date ? `Agendado · ${ticket.scheduled_date}` : 'Concluído'
      default:
        return 'Em análise'
    }
  }

  const isAwaitingApproval = ticket?.status === 'awaiting_adm_approval'
  const isResolved = ticket?.status === 'resolved' || ticket?.status === 'confirmed_schedule'

  async function handleApprove() {
    if (!selectedQuote || submitting) return
    setSubmitting(true)
    setErrorMsg(null)
    try {
      await onApprove(selectedQuote.provider_id)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Falha ao aprovar orçamento.'
      setErrorMsg(msg)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="adm-container" aria-label="Sessão Agente e Anfitrião: Comparativo de orçamentos">
      {/* Header do Mockup Orcamentos.dc.html */}
      <div className="adm-header-block">
        <div className="adm-top-row">
          {onBack && (
            <button
              type="button"
              className="back-btn"
              onClick={onBack}
              aria-label="Voltar para lista de chamados"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true">
                <path
                  d="M15 5 L8 12 L15 19"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </button>
          )}

          <span
            className={`status-pill ${
              isAwaitingApproval ? 'awaiting' : isResolved ? 'resolved' : 'neutral'
            }`}
          >
            {statusLabel()}
          </span>
        </div>

        <div className="adm-title-block">
          <span className="adm-subtitle">
            {property.title} · {property.neighborhood} · {ticket?.location_in_property || 'Geral'}
          </span>
          <h1>{ticket?.description || 'Nenhum chamado de manutenção em aberto'}</h1>
        </div>

        {ticket?.adm_synthesis ? (
          <p className="adm-synthesis-box">{ticket.adm_synthesis}</p>
        ) : isAwaitingApproval ? (
          <p className="adm-synthesis-box">
            Pedimos orçamento aos prestadores homologados da região. Analise as opções e aprove a melhor
            alternativa. O hóspede já foi acolhido.
          </p>
        ) : null}
      </div>

      {/* Trilha de Auditoria exibida somente quando houver eventos registrados */}
      {ticket && auditEvents.length > 0 && (
        <section
          style={{
            margin: '0 0 20px',
            padding: '16px 20px',
            background: 'var(--areia)',
            borderRadius: '16px',
            border: '1px solid var(--mar-08)',
          }}
          aria-label="Trilha de auditoria dos agentes"
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
            <h3 style={{ margin: 0, fontSize: '15px' }}>
              Como os agentes processaram este chamado
            </h3>
            <span className="tabular-nums" style={{ fontSize: '12px', color: 'var(--mar-72)', fontWeight: 600 }}>
              {auditEvents.length} etapa(s) registrada(s)
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {auditEvents.slice(0, 6).map((ev) => (
              <div
                key={ev.id}
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '4px',
                  padding: '8px 12px',
                  background: 'rgba(255, 255, 255, 0.85)',
                  borderRadius: '10px',
                  fontSize: '12px',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span className="audit-node" style={{ fontSize: '10px', padding: '2px 8px' }}>
                      {ev.node}
                    </span>
                    <strong>{ev.event_type}</strong>
                  </div>
                  <time className="tabular-nums" style={{ fontSize: '11px', color: 'var(--mar-72)' }}>
                    {new Date(ev.created_at).toLocaleTimeString('pt-BR')}
                  </time>
                </div>
                {ev.payload && Object.keys(ev.payload).length > 0 && (
                  <div style={{ fontSize: '11px', color: 'var(--mar-72)', marginTop: '2px' }}>
                    {Object.entries(ev.payload)
                      .slice(0, 3)
                      .map(([k, v]) => `${k}: ${typeof v === 'object' ? JSON.stringify(v) : String(v)}`)
                      .join(' · ')}
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Lista de Cotações Recebidas */}
      <div className="adm-quotes-list" role="radiogroup" aria-label="Opções de orçamento">
        {quotes.length === 0 ? (
          <div style={{ padding: '32px 16px', textAlign: 'center', color: 'var(--mar-72)', fontSize: '14px' }}>
            {ticket?.status === 'waiting_quotes'
              ? 'Aguardando retorno dos prestadores homologados...'
              : 'Nenhum orçamento disponível no momento.'}
          </div>
        ) : (
          quotes.map((quote, index) => {
            const isSelected = (selectedProviderId || quotes[0]?.provider_id) === quote.provider_id
            const name = quote.provider_name || `Prestador ${index + 1}`
            const rating = quote.provider_rating ? `${quote.provider_rating.toFixed(1)}` : '4.9'

            return (
              <div
                key={quote.id || quote.provider_id}
                role="radio"
                aria-checked={isSelected}
                tabIndex={0}
                className={`quote-card ${isSelected ? 'selected' : ''}`}
                onClick={() => {
                  if (isAwaitingApproval) setSelectedProviderId(quote.provider_id)
                }}
                onKeyDown={(e) => {
                  if ((e.key === ' ' || e.key === 'Enter') && isAwaitingApproval) {
                    setSelectedProviderId(quote.provider_id)
                  }
                }}
              >
                <div className="quote-card-header">
                  <div>
                    <h3 className="quote-provider-name">{name}</h3>
                    <span className="quote-provider-meta tabular-nums">
                      ★ {rating} · Prestador validado{quote.is_recommended ? ' · Melhor relação janela × preço' : ''}
                    </span>
                  </div>
                  <span className="quote-price tabular-nums">{money(quote.amount)}</span>
                </div>

                <div className="quote-chips">
                  {quote.proposed_availability && (
                    <span className="quote-chip">{quote.proposed_availability}</span>
                  )}
                  {quote.description && <span className="quote-chip">{quote.description}</span>}
                </div>
              </div>
            )
          })
        )}
      </div>

      {/* Rodapé e CTA de Aprovação */}
      <div className="adm-footer">
        {errorMsg && (
          <div
            style={{
              padding: '10px 14px',
              borderRadius: '10px',
              background: '#FDEDEC',
              color: '#C0392B',
              fontSize: '13px',
            }}
          >
            {errorMsg}
          </div>
        )}

        {isAwaitingApproval ? (
          <button
            type="button"
            className="primary-approve-btn"
            disabled={!selectedQuote || submitting || isLoading}
            onClick={handleApprove}
          >
            {submitting ? (
              'Destravando máquina de estados...'
            ) : selectedQuote ? (
              `Aprovar ${selectedQuote.provider_name || 'prestador'} · ${money(selectedQuote.amount)}`
            ) : (
              'Selecione um orçamento'
            )}
          </button>
        ) : isResolved ? (
          <div
            style={{
              padding: '16px',
              background: 'var(--mar-08)',
              borderRadius: '14px',
              textAlign: 'center',
              fontSize: '14px',
              fontWeight: 600,
            }}
          >
            ✓ Orçamento aprovado e agendamento confirmado!
          </div>
        ) : null}

        <span className="adm-guarantee-note">
          A Zelo agenda e avisa o hóspede. Nada é contratado sem você.
        </span>
      </div>
    </div>
  )
}

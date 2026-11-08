import { useState } from 'react'
import { formatFriendlyDate, type MaintenanceTicket, type Property, type Quote } from '../contracts'

const money = (val: number | null | undefined) =>
  val != null
    ? new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 }).format(val)
    : 'A combinar'

interface QuotesComparisonProps {
  property: Property
  ticket: MaintenanceTicket | null
  quotes: Quote[]
  onApprove: (providerId: string) => Promise<void>
  onRejectQuotes?: (reason: string) => Promise<void>
  onBack?: () => void
  isLoading?: boolean
}

export function QuotesComparison({
  property,
  ticket,
  quotes,
  onApprove,
  onRejectQuotes,
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
  const [rejectingMode, setRejectingMode] = useState(false)
  const [rejectReason, setRejectReason] = useState(
    'Gostaria de propostas com menor custo ou atendimento mais rápido.',
  )
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

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
        return ticket.scheduled_date
          ? `Agendado · ${formatFriendlyDate(ticket.scheduled_date)}`
          : 'Concluído'
      default:
        return 'Em análise'
    }
  }

  const isAwaitingApproval = ticket?.status === 'awaiting_adm_approval'
  const isResolved = ticket?.status === 'resolved' || ticket?.status === 'confirmed_schedule'

  const synthesisText = (() => {
    if (isResolved) {
      return 'Orçamento aprovado pelo anfitrião. A visita técnica foi agendada e o prestador homologado já foi acionado para o atendimento no imóvel. O hóspede foi comunicado.'
    }
    if (
      ticket?.adm_synthesis &&
      !ticket.adm_synthesis.includes('determinística') &&
      !ticket.adm_synthesis.includes('resolver_adm_summary') &&
      !ticket.adm_synthesis.includes('nó')
    ) {
      return ticket.adm_synthesis
    }
    return 'Pedimos orçamento aos prestadores homologados da região. Analise as opções e aprove a melhor alternativa. O hóspede já foi acolhido.'
  })()

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

  async function handleRejectAllQuotes() {
    if (!onRejectQuotes || submitting) return
    setSubmitting(true)
    setErrorMsg(null)
    try {
      await onRejectQuotes(rejectReason.trim())
      setRejectingMode(false)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Falha ao solicitar novos orçamentos.'
      setErrorMsg(msg)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="adm-container" aria-label="Sessão Agente e Anfitrião: Comparativo de orçamentos">
      {/* Header com identificação e status amigável */}
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

        {synthesisText && (
          <div className="adm-synthesis-box">
            <p style={{ margin: 0 }}>{synthesisText}</p>
          </div>
        )}
      </div>

      {/* Banner de Confirmação quando já agendado */}
      {isResolved && (
        <div
          style={{
            margin: '20px 20px 0',
            padding: '16px 20px',
            background: 'var(--mar-08)',
            borderRadius: '16px',
            display: 'flex',
            gap: '14px',
            alignItems: 'center',
          }}
        >
          <div
            style={{
              width: '32px',
              height: '32px',
              borderRadius: '50%',
              background: 'var(--mar-profundo)',
              color: '#fff',
              display: 'grid',
              placeItems: 'center',
              fontWeight: 800,
              fontSize: '16px',
              flexShrink: 0,
            }}
          >
            ✓
          </div>
          <div>
            <strong style={{ display: 'block', fontSize: '15px', color: 'var(--mar-profundo)' }}>
              Visita técnica agendada com sucesso!
            </strong>
            <span style={{ fontSize: '13px', color: 'var(--mar-72)' }}>
              Prestador: <strong>{selectedQuote?.provider_name || 'Prestador Homologado'}</strong> ·{' '}
              {ticket?.scheduled_date && (
                <span>Visita em <strong>{formatFriendlyDate(ticket.scheduled_date)}</strong></span>
              )}
            </span>
          </div>
        </div>
      )}

      {/* Comparativo de Orçamentos Recebidos */}
      <div className="adm-quotes-list" role="radiogroup" aria-label="Opções de orçamento">
        {quotes.length === 0 ? (
          <div style={{ padding: '32px 16px', textAlign: 'center', color: 'var(--mar-72)', fontSize: '14px' }}>
            {ticket?.status === 'waiting_quotes'
              ? 'Buscando orçamentos com os prestadores homologados...'
              : 'Nenhum orçamento disponível no momento.'}
          </div>
        ) : (
          quotes.map((quote, index) => {
            const isSelected = (selectedProviderId || quotes[0]?.provider_id) === quote.provider_id
            const name = quote.provider_name || `Prestador ${index + 1}`
            const rating =
              quote.provider_rating != null ? `${quote.provider_rating.toFixed(1)}` : '4.8'
            const reviewsLabel =
              quote.provider_reviews_count != null
                ? ` (${quote.provider_reviews_count} avaliações no Google)`
                : ''

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
                      ★ {rating}{reviewsLabel} · Prestador homologado
                      {quote.is_recommended ? ' · Melhor relação nota × custo' : ''}
                    </span>
                    {quote.provider_address && (
                      <span
                        style={{
                          display: 'block',
                          fontSize: '12px',
                          color: 'var(--mar-72)',
                          marginTop: '3px',
                        }}
                      >
                        {quote.provider_address}
                      </span>
                    )}
                  </div>
                  <span className="quote-price tabular-nums">{money(quote.amount)}</span>
                </div>

                <div className="quote-chips">
                  {quote.proposed_availability && (
                    <span className="quote-chip">
                      Disponibilidade: {formatFriendlyDate(quote.proposed_availability)}
                    </span>
                  )}
                  {quote.description && <span className="quote-chip">{quote.description}</span>}
                  {isSelected && isResolved && (
                    <span className="quote-chip" style={{ background: 'var(--mar-profundo)', color: '#fff' }}>
                      ✓ Escolhido pelo anfitrião
                    </span>
                  )}
                </div>
              </div>
            )
          })
        )}
      </div>

      {/* Rodapé com CTA de Aprovação Clara */}
      <div className="adm-footer">
        {errorMsg && (
          <div
            role="alert"
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
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', width: '100%' }}>
            <button
              type="button"
              className="primary-approve-btn"
              disabled={!selectedQuote || submitting || isLoading}
              onClick={handleApprove}
            >
              {submitting ? (
                'Processando decisão...'
              ) : selectedQuote ? (
                `Aprovar ${selectedQuote.provider_name || 'prestador'} · ${money(selectedQuote.amount)}`
              ) : (
                'Selecione um orçamento'
              )}
            </button>

            {onRejectQuotes && !rejectingMode && (
              <button
                type="button"
                className="action-secondary"
                disabled={submitting || isLoading}
                onClick={() => setRejectingMode(true)}
                style={{ width: '100%', justifyContent: 'center' }}
              >
                Recusar propostas e solicitar novos orçamentos
              </button>
            )}

            {onRejectQuotes && rejectingMode && (
              <div
                style={{
                  padding: '12px',
                  borderRadius: '10px',
                  border: '1px solid var(--mar-24)',
                  background: '#fff',
                }}
              >
                <label
                  style={{
                    display: 'block',
                    fontSize: '12px',
                    fontWeight: 600,
                    marginBottom: '6px',
                  }}
                >
                  Orientação para o agente renegociar / buscar novas propostas:
                </label>
                <input
                  type="text"
                  value={rejectReason}
                  onChange={(e) => setRejectReason(e.target.value)}
                  placeholder="Informe o motivo da recusa dos orçamentos..."
                  style={{
                    width: '100%',
                    padding: '8px 10px',
                    borderRadius: '8px',
                    border: '1px solid var(--mar-24)',
                    marginBottom: '8px',
                  }}
                />
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button
                    type="button"
                    className="action-primary"
                    disabled={submitting || !rejectReason.trim()}
                    onClick={() => void handleRejectAllQuotes()}
                  >
                    {submitting ? 'Solicitando...' : 'Confirmar e pedir novas propostas'}
                  </button>
                  <button
                    type="button"
                    className="action-secondary"
                    disabled={submitting}
                    onClick={() => setRejectingMode(false)}
                  >
                    Cancelar
                  </button>
                </div>
              </div>
            )}
          </div>
        ) : isResolved ? (
          <div
            style={{
              padding: '16px',
              background: 'var(--mar-08)',
              borderRadius: '14px',
              textAlign: 'center',
              fontSize: '14px',
              fontWeight: 600,
              color: 'var(--mar-profundo)',
            }}
          >
            ✓ Orçamento aprovado e agendamento confirmado!
          </div>
        ) : null}

        <span className="adm-guarantee-note">
          A Zelo agenda e avisa o hóspede. Nada é contratado sem sua aprovação prévia.
        </span>
      </div>
    </div>
  )
}

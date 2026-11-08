import { useEffect, useState } from 'react'
import {
  approveBooking,
  approveQuote,
  fetchPropertyBookings,
  fetchQuotes,
  fetchTicketsForProperty,
  rejectBooking,
} from '../api/client'
import {
  formatFriendlyDate,
  type BookingItem,
  type ChatMessage,
  type MaintenanceTicket,
  type Property,
  type PropertyTab,
  type Quote,
} from '../contracts'
import { propertyUrl } from '../routes'
import { ChatPanel } from './ChatPanel'
import { QuotesComparison } from './QuotesComparison'
import { ProviderSimulator } from './ProviderSimulator'

const moneyBrl = (value: number) =>
  new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value)

const formatBrDate = (isoDate: string) => {
  const parts = isoDate.split('-')
  if (parts.length === 3) return `${parts[2]}/${parts[1]}/${parts[0]}`
  return isoDate
}

const calcNights = (start: string, end: string) => {
  const d1 = new Date(`${start}T12:00:00`)
  const d2 = new Date(`${end}T12:00:00`)
  const diff = Math.round((d2.getTime() - d1.getTime()) / (1000 * 60 * 60 * 24))
  return Math.max(1, diff)
}

export function PropertyWorkspace({
  property,
  tab,
  messages,
  onNewMessage,
}: {
  property: Property
  tab: PropertyTab
  messages: ChatMessage[]
  onNewMessage: (msg: ChatMessage) => void
}) {
  const [snapshot, setSnapshot] = useState<{
    propertyId: string
    ticket: MaintenanceTicket | null
    quotes: Quote[]
    bookings: BookingItem[]
  }>({ propertyId: property.id, ticket: null, quotes: [], bookings: [] })
  const [loadingQuotes, setLoadingQuotes] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [revision, setRevision] = useState(0)

  // Estado para aprovação/recusa de reservas pelo anfitrião
  const [rejectingBookingId, setRejectingBookingId] = useState<string | null>(null)
  const [rejectionReason, setRejectionReason] = useState('')
  const [customPrices, setCustomPrices] = useState<Record<string, string>>({})
  const [bookingFeedback, setBookingFeedback] = useState('')
  const [bookingBusyId, setBookingBusyId] = useState<string | null>(null)

  const ticket = snapshot.propertyId === property.id ? snapshot.ticket : null
  const quotes = snapshot.propertyId === property.id ? snapshot.quotes : []
  const bookings = snapshot.propertyId === property.id ? snapshot.bookings : []
  const pendingBookings = bookings.filter((b) => b.status === 'pending_approval')

  const scheduledDate =
    ticket?.scheduled_date &&
    ['confirmed_schedule', 'notifying_tenant', 'resolved'].includes(ticket.status)
      ? ticket.scheduled_date
      : null

  function loadTicketData() {
    setLoadingQuotes(true)
    setRevision((previous) => previous + 1)
  }

  useEffect(() => {
    let active = true
    let inFlight = false
    async function refresh() {
      if (inFlight) return
      inFlight = true
      try {
        const [tickets, propBookings] = await Promise.all([
          fetchTicketsForProperty(property.id),
          fetchPropertyBookings(property.id),
        ])
        const current = tickets[0] ?? null
        const currentQuotes = current ? await fetchQuotes(current.id) : []
        if (!active) return
        setSnapshot({
          propertyId: property.id,
          ticket: current,
          quotes: currentQuotes,
          bookings: propBookings,
        })
        setLoadError('')
      } catch (cause) {
        if (active) {
          setLoadError(
            cause instanceof Error ? cause.message : 'Não foi possível atualizar o atendimento.',
          )
        }
      } finally {
        inFlight = false
        if (active) setLoadingQuotes(false)
      }
    }
    const refreshOnFocus = () => {
      void refresh()
    }
    void refresh()
    const timer = window.setInterval(refreshOnFocus, 5000)
    window.addEventListener('focus', refreshOnFocus)
    return () => {
      active = false
      window.clearInterval(timer)
      window.removeEventListener('focus', refreshOnFocus)
    }
  }, [property.id, revision, tab])

  async function handleApprove(providerId: string) {
    if (!ticket) return
    const updated = await approveQuote(ticket.id, providerId, ticket.run_id)
    setSnapshot((previous) => ({ ...previous, ticket: updated }))
    loadTicketData()
  }

  async function handleApproveBooking(booking: BookingItem) {
    setBookingBusyId(booking.id)
    setBookingFeedback('')
    try {
      const rawCustom = customPrices[booking.id]
      const parsedPrice = rawCustom ? Number(rawCustom) : booking.total_price ?? undefined
      const finalPrice =
        parsedPrice && !Number.isNaN(parsedPrice) && parsedPrice > 0 ? parsedPrice : undefined
      const approved = await approveBooking(booking.id, finalPrice)
      const nights = calcNights(approved.start_date, approved.end_date)
      const priceValue = approved.total_price ?? nights * property.nightlyRate

      onNewMessage({
        id: crypto.randomUUID(),
        propertyId: property.id,
        channel: 'guest',
        sender: 'agent',
        body: `Excelente notícia! O anfitrião aprovou sua reserva para o imóvel '${property.title}' de ${formatBrDate(approved.start_date)} a ${formatBrDate(approved.end_date)} (${nights} ${nights === 1 ? 'diária' : 'diárias'}) pelo valor de ${moneyBrl(priceValue)}. Sua estadia está confirmada!`,
        time: new Intl.DateTimeFormat('pt-BR', { hour: '2-digit', minute: '2-digit' }).format(
          new Date(),
        ),
        bookingId: approved.id,
      })
      setBookingFeedback(
        `Reserva de ${approved.guest_name} (${formatBrDate(approved.start_date)} a ${formatBrDate(approved.end_date)}) confirmada por ${moneyBrl(priceValue)}!`,
      )
      loadTicketData()
    } catch (cause) {
      setLoadError(cause instanceof Error ? cause.message : 'Falha ao aprovar reserva.')
    } finally {
      setBookingBusyId(null)
    }
  }

  async function handleRejectBooking(booking: BookingItem) {
    const reason = rejectionReason.trim() || 'Período indisponível na agenda do anfitrião.'
    setBookingBusyId(booking.id)
    setBookingFeedback('')
    try {
      const rejected = await rejectBooking(booking.id, reason)
      onNewMessage({
        id: crypto.randomUUID(),
        propertyId: property.id,
        channel: 'guest',
        sender: 'agent',
        body: `Atualização sobre sua solicitação para '${property.title}' (${formatBrDate(rejected.start_date)} a ${formatBrDate(rejected.end_date)}): o anfitrião não pôde aceitar a reserva para este período. Motivo informado: ${reason}. Gostaria de verificar outras datas disponíveis?`,
        time: new Intl.DateTimeFormat('pt-BR', { hour: '2-digit', minute: '2-digit' }).format(
          new Date(),
        ),
        bookingId: rejected.id,
      })
      setRejectingBookingId(null)
      setRejectionReason('')
      setBookingFeedback(
        `Solicitação de ${rejected.guest_name} recusada. O hóspede foi notificado no chat.`,
      )
      loadTicketData()
    } catch (cause) {
      setLoadError(cause instanceof Error ? cause.message : 'Falha ao recusar reserva.')
    } finally {
      setBookingBusyId(null)
    }
  }

  const wifiSsid = property.id === 'prop-portodigital-04' ? 'PortoDigital_Tech' : 'Zelo_Hospedes'
  const isPortoDigital = property.id === 'prop-portodigital-04'

  return (
    <div className="tab-content">
      {loadError && (
        <div role="alert" className="form-error">
          <p>{loadError}</p>
          <button type="button" className="action-secondary" onClick={loadTicketData}>
            Atualizar atendimento
          </button>
        </div>
      )}
      {tab === 'chat' && (
        <div className="split-layout">
          <ChatPanel
            property={property}
            messages={messages}
            onNewMessage={onNewMessage}
            onTicketCreated={() => loadTicketData()}
            onBookingCreated={() => loadTicketData()}
            scheduledVisit={scheduledDate ? formatFriendlyDate(scheduledDate) : null}
          />
          <aside style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {/* 1. Guia minimalista do imóvel */}
            <div className="property-guide-card">
              <div className="property-guide-header">
                <img src={property.image} alt={property.title} className="property-guide-thumb" />
                <div>
                  <span className="eyebrow" style={{ fontSize: '10px' }}>
                    GUIA DO IMÓVEL
                  </span>
                  <h3>{property.title}</h3>
                  <p>
                    {property.neighborhood} · {property.location.split(',')[1]?.trim() || 'Brasil'}
                  </p>
                </div>
              </div>

              <div className="guide-items">
                <div className="guide-item">
                  <div className="guide-meta-col">
                    <span className="guide-kicker">Diária base</span>
                    <p className="guide-value">
                      <strong>{moneyBrl(property.nightlyRate)}</strong> por noite · Sujeito a aceite
                      do anfitrião
                    </p>
                  </div>
                </div>
                <div className="guide-item">
                  <div className="guide-meta-col">
                    <span className="guide-kicker">Wi-Fi da acomodação</span>
                    <p className="guide-value">
                      Rede <strong>{wifiSsid}</strong> · Senha <strong>zelo@2026</strong>
                    </p>
                  </div>
                </div>
                <div className="guide-item">
                  <div className="guide-meta-col">
                    <span className="guide-kicker">Acesso</span>
                    <p className="guide-value">
                      {isPortoDigital
                        ? 'Fechadura digital com código autônomo 24h'
                        : 'Check-in autônomo com anfitrião'}
                    </p>
                  </div>
                </div>
                <div className="guide-item">
                  <div className="guide-meta-col">
                    <span className="guide-kicker">Horários de estadia</span>
                    <p className="guide-value">Check-in a partir das 14h · Check-out até 11h</p>
                  </div>
                </div>
              </div>

              <div className="guide-footer-tip">
                <small>
                  Solicitações de reserva e chamados de manutenção passam pela aprovação do anfitrião
                  na aba Agente ⇄ Anfitrião.
                </small>
              </div>
            </div>

            {/* 2. Solicitação de Hospedagem Pendente (se houver) */}
            {pendingBookings.length > 0 && (
              <div className="active-ticket-mini-card">
                <div className="ticket-mini-top">
                  <span className="status-pill awaiting">Hospedagem aguardando aceite</span>
                  <span className="ticket-loc">{pendingBookings.length} pendente(s)</span>
                </div>
                <h4>
                  {pendingBookings[0]!.guest_name} · {formatBrDate(pendingBookings[0]!.start_date)} a{' '}
                  {formatBrDate(pendingBookings[0]!.end_date)}
                </h4>
                <p className="ticket-date">
                  Valor proposto:{' '}
                  <strong>
                    {moneyBrl(
                      pendingBookings[0]!.total_price ??
                        calcNights(pendingBookings[0]!.start_date, pendingBookings[0]!.end_date) *
                          property.nightlyRate,
                    )}
                  </strong>
                </p>
                <div style={{ marginTop: '10px' }}>
                  <a
                    href={propertyUrl(property.id, 'adm')}
                    className="shortcut-btn primary"
                    style={{ fontSize: '12px', padding: '8px 12px', display: 'inline-block' }}
                    onClick={(e) => {
                      e.preventDefault()
                      window.history.pushState(null, '', propertyUrl(property.id, 'adm'))
                      window.dispatchEvent(new PopStateEvent('popstate'))
                    }}
                  >
                    Aceitar ou Recusar em Agente ⇄ Anfitrião →
                  </a>
                </div>
              </div>
            )}

            {/* 3. Chamado Ativo do Imóvel (se houver) */}
            {ticket && (
              <div className="active-ticket-mini-card">
                <div className="ticket-mini-top">
                  <span
                    className={`status-pill ${
                      ticket.status === 'awaiting_adm_approval'
                        ? 'awaiting'
                        : ticket.status === 'resolved' || ticket.status === 'confirmed_schedule'
                        ? 'resolved'
                        : 'neutral'
                    }`}
                  >
                    {ticket.status === 'awaiting_adm_approval'
                      ? 'Aguardando sua decisão'
                      : ticket.status === 'resolved' || ticket.status === 'confirmed_schedule'
                      ? 'Visita agendada'
                      : 'Em andamento'}
                  </span>
                  <span className="ticket-loc">{ticket.location_in_property || 'Geral'}</span>
                </div>
                <h4>{ticket.description}</h4>
                {ticket.scheduled_date && (
                  <p className="ticket-date">
                    Data da visita: <strong>{formatFriendlyDate(ticket.scheduled_date)}</strong>
                  </p>
                )}
                <div style={{ marginTop: '10px' }}>
                  <a
                    href={propertyUrl(property.id, 'adm')}
                    className="shortcut-btn primary"
                    style={{ fontSize: '12px', padding: '8px 12px', display: 'inline-block' }}
                    onClick={(e) => {
                      e.preventDefault()
                      window.history.pushState(null, '', propertyUrl(property.id, 'adm'))
                      window.dispatchEvent(new PopStateEvent('popstate'))
                    }}
                  >
                    Ver detalhes em Agente ⇄ Anfitrião →
                  </a>
                </div>
              </div>
            )}
          </aside>
        </div>
      )}

      {tab === 'adm' && (
        <div className="split-layout">
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
            {/* Governança de Reservas do Anfitrião */}
            <section
              className="adm-control-card"
              aria-label="Solicitações de hospedagem do imóvel"
            >
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  marginBottom: '12px',
                }}
              >
                <div>
                  <span className="eyebrow">GOVERNANÇA DE HOSPEDAGEM</span>
                  <h3 style={{ margin: '4px 0 0', fontSize: '18px' }}>
                    Solicitações de Reserva ({pendingBookings.length} pendente
                    {pendingBookings.length === 1 ? '' : 's'})
                  </h3>
                </div>
              </div>

              {bookingFeedback && (
                <p
                  role="status"
                  style={{
                    background: 'var(--mar-08)',
                    padding: '10px 14px',
                    borderRadius: '8px',
                    fontSize: '13px',
                    fontWeight: 600,
                    marginBottom: '12px',
                  }}
                >
                  {bookingFeedback}
                </p>
              )}

              {pendingBookings.length === 0 ? (
                <p style={{ margin: 0, fontSize: '13px', color: 'var(--mar-72)' }}>
                  Nenhuma solicitação de reserva pendente no momento. Quando um cliente solicitar
                  datas disponíveis no Chat do Imóvel, você poderá aceitar pelo valor proposto ou
                  recusar com justificativa aqui.
                </p>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                  {pendingBookings.map((b) => {
                    const nights = calcNights(b.start_date, b.end_date)
                    const defaultPrice = b.total_price ?? nights * property.nightlyRate
                    const customVal = customPrices[b.id] ?? String(defaultPrice)
                    const isRejecting = rejectingBookingId === b.id
                    const isBusy = bookingBusyId === b.id

                    return (
                      <div
                        key={b.id}
                        style={{
                          border: '1px solid var(--mar-24)',
                          borderRadius: '12px',
                          padding: '14px 16px',
                          background: '#fff',
                        }}
                      >
                        <div
                          style={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'flex-start',
                            gap: '12px',
                            flexWrap: 'wrap',
                          }}
                        >
                          <div>
                            <span className="status-pill awaiting">Aguardando aprovação</span>
                            <h4 style={{ margin: '8px 0 4px', fontSize: '16px' }}>
                              {b.guest_name} · {b.num_guests ?? 2} hóspede(s)
                            </h4>
                            <p style={{ margin: 0, fontSize: '13px', color: 'var(--mar-72)' }}>
                              Check-in: <strong>{formatBrDate(b.start_date)}</strong> → Check-out:{' '}
                              <strong>{formatBrDate(b.end_date)}</strong> ({nights}{' '}
                              {nights === 1 ? 'diária' : 'diárias'})
                            </p>
                          </div>

                          <div style={{ textAlign: 'right' }}>
                            <label
                              style={{
                                display: 'block',
                                fontSize: '11px',
                                color: 'var(--mar-72)',
                                marginBottom: '4px',
                              }}
                            >
                              Valor da estadia (R$)
                            </label>
                            <input
                              type="number"
                              min={50}
                              step={10}
                              aria-label={`Valor da estadia para ${b.guest_name}`}
                              value={customVal}
                              onChange={(e) =>
                                setCustomPrices((prev) => ({ ...prev, [b.id]: e.target.value }))
                              }
                              style={{
                                width: '120px',
                                padding: '6px 10px',
                                borderRadius: '8px',
                                border: '1px solid var(--mar-24)',
                                fontWeight: 700,
                                textAlign: 'right',
                              }}
                            />
                          </div>
                        </div>

                        {!isRejecting ? (
                          <div
                            style={{
                              display: 'flex',
                              gap: '10px',
                              marginTop: '14px',
                              flexWrap: 'wrap',
                            }}
                          >
                            <button
                              type="button"
                              className="action-primary"
                              disabled={isBusy}
                              onClick={() => void handleApproveBooking(b)}
                            >
                              {isBusy
                                ? 'Processando...'
                                : `Aceitar Reserva (${moneyBrl(Number(customVal) || defaultPrice)})`}
                            </button>
                            <button
                              type="button"
                              className="action-secondary"
                              disabled={isBusy}
                              onClick={() => {
                                setRejectingBookingId(b.id)
                                setRejectionReason('Imóvel em manutenção preventiva no período.')
                              }}
                            >
                              Recusar com motivo
                            </button>
                          </div>
                        ) : (
                          <div
                            style={{
                              marginTop: '14px',
                              paddingTop: '12px',
                              borderTop: '1px solid var(--mar-12)',
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
                              Motivo da recusa (será enviado ao hóspede no chat):
                            </label>
                            <input
                              type="text"
                              value={rejectionReason}
                              onChange={(e) => setRejectionReason(e.target.value)}
                              placeholder="Informe o motivo da recusa..."
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
                                disabled={isBusy || !rejectionReason.trim()}
                                onClick={() => void handleRejectBooking(b)}
                              >
                                Confirmar Recusa
                              </button>
                              <button
                                type="button"
                                className="action-secondary"
                                disabled={isBusy}
                                onClick={() => setRejectingBookingId(null)}
                              >
                                Cancelar
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              )}
            </section>

            <QuotesComparison
              key={ticket?.id ?? property.id}
              property={property}
              ticket={ticket}
              quotes={quotes}
              onApprove={handleApprove}
              isLoading={loadingQuotes}
            />
          </div>
          <aside style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {ticket && (
              <details className="adm-control-card">
                <summary>Ações do prestador (demonstração)</summary>
                <ProviderSimulator
                  key={ticket.id}
                  property={property}
                  currentTicketId={ticket.id}
                  ticketStatus={ticket.status}
                  onTicketUpdated={loadTicketData}
                  providerOnly
                />
              </details>
            )}
            {/* 1. Painel de Controle e Garantias do Anfitrião */}
            <div className="adm-control-card">
              <span className="eyebrow">ÁREA DO ANFITRIÃO</span>
              <h3 style={{ margin: '4px 0 10px', fontSize: '18px' }}>Decisões com você</h3>
              <p
                style={{
                  margin: '0 0 16px',
                  fontSize: '13px',
                  color: 'var(--mar-72)',
                  lineHeight: 1.5,
                }}
              >
                Somente as decisões deste imóvel aparecem aqui. O agente valida datas de reserva e
                reúne orçamentos de manutenção aguardando sua escolha explícita.
              </p>

              <div className="adm-guarantees-list">
                <div className="guarantee-item">
                  <span className="guarantee-bullet" />
                  <div>
                    <strong>Você tem o controle</strong>
                    <p>Nenhuma reserva ou prestador é confirmado sem seu clique e aprovação prévia.</p>
                  </div>
                </div>
                <div className="guarantee-item">
                  <span className="guarantee-bullet" />
                  <div>
                    <strong>Prestadores homologados</strong>
                    <p>Profissionais validados na região com avaliação média comprovada.</p>
                  </div>
                </div>
                <div className="guarantee-item">
                  <span className="guarantee-bullet" />
                  <div>
                    <strong>Proteção de estadias</strong>
                    <p>A janela da visita é calculada para não coincidir com a rotina de hóspedes.</p>
                  </div>
                </div>
              </div>

              <div
                style={{
                  marginTop: '16px',
                  paddingTop: '14px',
                  borderTop: '1px solid var(--mar-16)',
                }}
              >
                <a
                  href="/agentes"
                  style={{
                    fontSize: '12px',
                    fontWeight: 700,
                    color: 'var(--mar-profundo)',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '4px',
                  }}
                  onClick={(e) => {
                    e.preventDefault()
                    window.history.pushState(null, '', '/agentes')
                    window.dispatchEvent(new PopStateEvent('popstate'))
                  }}
                >
                  Ver fluxo no Grafo de Agentes →
                </a>
              </div>
            </div>
          </aside>
        </div>
      )}
    </div>
  )
}

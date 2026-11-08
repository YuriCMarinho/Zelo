import { useEffect, useState } from 'react'
import { approveQuote, fetchQuotes, fetchTicketsForProperty } from '../api/client'
import { formatFriendlyDate, type ChatMessage, type MaintenanceTicket, type Property, type PropertyTab, type Quote } from '../contracts'
import { propertyUrl } from '../routes'
import { ChatPanel } from './ChatPanel'
import { QuotesComparison } from './QuotesComparison'
import { ProviderSimulator } from './ProviderSimulator'

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
    propertyId: string; ticket: MaintenanceTicket | null; quotes: Quote[]
  }>({ propertyId: property.id, ticket: null, quotes: [] })
  const [loadingQuotes, setLoadingQuotes] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [revision, setRevision] = useState(0)
  const ticket = snapshot.propertyId === property.id ? snapshot.ticket : null
  const quotes = snapshot.propertyId === property.id ? snapshot.quotes : []
  const scheduledDate = ticket?.scheduled_date &&
    ['confirmed_schedule', 'notifying_tenant', 'resolved'].includes(ticket.status)
    ? ticket.scheduled_date : null

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
        const tickets = await fetchTicketsForProperty(property.id)
        const current = tickets[0] ?? null
        const currentQuotes = current ? await fetchQuotes(current.id) : []
        if (!active) return
        setSnapshot({ propertyId: property.id, ticket: current, quotes: currentQuotes })
        setLoadError('')
      } catch (cause) {
        if (active) {
          setLoadError(cause instanceof Error ? cause.message : 'Não foi possível atualizar o atendimento.')
        }
      } finally {
        inFlight = false
        if (active) setLoadingQuotes(false)
      }
    }
    const refreshOnFocus = () => { void refresh() }
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

  const wifiSsid = property.id === 'prop-portodigital-04' ? 'PortoDigital_Tech' : 'Zelo_Hospedes'
  const isPortoDigital = property.id === 'prop-portodigital-04'

  return (
    <div className="tab-content">
      {loadError && <div role="alert" className="form-error">
        <p>{loadError}</p>
        <button type="button" className="action-secondary" onClick={loadTicketData}>Atualizar atendimento</button>
      </div>}
      {tab === 'chat' && (
        <div className="split-layout">
          <ChatPanel
            property={property}
            messages={messages}
            onNewMessage={onNewMessage}
            onTicketCreated={() => loadTicketData()}
            scheduledVisit={scheduledDate ? formatFriendlyDate(scheduledDate) : null}
          />
          <aside style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {/* 1. Guia minimalista do imóvel com informações essenciais da estadia (sem emojis) */}
            <div className="property-guide-card">
              <div className="property-guide-header">
                <img src={property.image} alt={property.title} className="property-guide-thumb" />
                <div>
                  <span className="eyebrow" style={{ fontSize: '10px' }}>GUIA DO IMÓVEL</span>
                  <h3>{property.title}</h3>
                  <p>{property.neighborhood} · {property.location.split(',')[1]?.trim() || 'Brasil'}</p>
                </div>
              </div>

              <div className="guide-items">
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
                      {isPortoDigital ? 'Fechadura digital com código autônomo 24h' : 'Check-in autônomo com anfitrião'}
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
                  Dúvidas rotineiras são respondidas pela IA no chat. Problemas no imóvel geram chamados para o anfitrião aprovar.
                </small>
              </div>
            </div>

            {/* 2. Chamado Ativo do Imóvel (se houver, limpo e sem emojis) */}
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
          <QuotesComparison
            key={ticket?.id ?? property.id}
            property={property}
            ticket={ticket}
            quotes={quotes}
            onApprove={handleApprove}
            isLoading={loadingQuotes}
          />
          <aside style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {ticket && <details className="adm-control-card">
              <summary>Ações do prestador (demonstração)</summary>
              <ProviderSimulator
                key={ticket.id}
                property={property}
                currentTicketId={ticket.id}
                ticketStatus={ticket.status}
                onTicketUpdated={loadTicketData}
                providerOnly
              />
            </details>}
            {/* 1. Painel de Controle e Garantias do Anfitrião (limpo, minimalista, sem emojis) */}
            <div className="adm-control-card">
              <span className="eyebrow">ÁREA DO ANFITRIÃO</span>
              <h3 style={{ margin: '4px 0 10px', fontSize: '18px' }}>Decisões com você</h3>
              <p style={{ margin: '0 0 16px', fontSize: '13px', color: 'var(--mar-72)', lineHeight: 1.5 }}>
                Somente as decisões deste imóvel aparecem aqui. O agente reúne orçamentos e aguarda sua escolha explícita.
              </p>

              <div className="adm-guarantees-list">
                <div className="guarantee-item">
                  <span className="guarantee-bullet" />
                  <div>
                    <strong>Você tem o controle</strong>
                    <p>Nenhum prestador é contratado sem seu clique e aprovação prévia.</p>
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

              <div style={{ marginTop: '16px', paddingTop: '14px', borderTop: '1px solid var(--mar-16)' }}>
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

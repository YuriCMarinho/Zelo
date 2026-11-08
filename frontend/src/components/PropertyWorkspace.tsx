import { useEffect, useState } from 'react'
import { approveQuote, fetchQuotes, fetchTicketsForProperty } from '../api/client'
import { formatFriendlyDate, type ChatMessage, type MaintenanceTicket, type Property, type PropertyTab, type Quote } from '../contracts'
import { propertyUrl } from '../routes'
import { ChatPanel } from './ChatPanel'
import { QuotesComparison } from './QuotesComparison'

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
  const [ticket, setTicket] = useState<MaintenanceTicket | null>(null)
  const [quotes, setQuotes] = useState<Quote[]>([])
  const [loadingQuotes, setLoadingQuotes] = useState(false)
  const [scheduledDate, setScheduledDate] = useState<string | null>(null)

  // Carrega chamados reais do imóvel
  const loadTicketData = () => {
    fetchTicketsForProperty(property.id)
      .then(async (tickets) => {
        const active = tickets[0]
        if (active) {
          setTicket(active)
          if (active.scheduled_date) setScheduledDate(active.scheduled_date)
          const qList = await fetchQuotes(active.id)
          setQuotes(qList)
        } else if (property.id === 'casa-aurora') {
          // mantem em caso de teste offline
        } else {
          setTicket(null)
          setQuotes([])
        }
      })
      .catch(() => {})
  }

  useEffect(() => {
    let ignore = false
    fetchTicketsForProperty(property.id)
      .then(async (tickets) => {
        if (ignore) return
        const active = tickets[0]
        if (active) {
          setTicket(active)
          if (active.scheduled_date) {
            setScheduledDate(active.scheduled_date)
          }
          setLoadingQuotes(true)
          const qList = await fetchQuotes(active.id)
          if (!ignore) {
            setQuotes(qList)
            setLoadingQuotes(false)
          }
        } else if (property.id === 'casa-aurora') {
          setTicket({
            id: 'tick-demo-302',
            run_id: 'run-demo-001',
            property_id: property.id,
            reported_by_role: 'tenant',
            category: 'eletricista',
            urgency: 'normal',
            location_in_property: 'Banheiro',
            description: 'Chuveiro sem água quente',
            status: 'awaiting_adm_approval',
            adm_synthesis:
              'Pedimos orçamento a 5 eletricistas da região. 3 responderam. O hóspede já foi avisado de que estamos cuidando.',
            notify_tenant: true,
            created_at: new Date().toISOString(),
          })
          setQuotes([
            {
              id: 'q-carlos',
              ticket_id: 'tick-demo-302',
              run_id: 'run-demo-001',
              provider_id: 'prov-carlos',
              provider_name: 'Carlos Eletricista',
              provider_rating: 4.9,
              amount: 180,
              proposed_availability: 'Amanhã, 9h',
              description: 'Hóspede sai às 11h',
              status: 'received',
              is_recommended: true,
            },
            {
              id: 'q-volt',
              ticket_id: 'tick-demo-302',
              run_id: 'run-demo-001',
              provider_id: 'prov-volt',
              provider_name: 'Volt Reparos',
              provider_rating: 4.7,
              amount: 240,
              proposed_availability: 'Hoje, 17h',
              status: 'received',
            },
            {
              id: 'q-joao',
              ticket_id: 'tick-demo-302',
              run_id: 'run-demo-001',
              provider_id: 'prov-joao',
              provider_name: 'João Faz-Tudo',
              provider_rating: 4.5,
              amount: 150,
              proposed_availability: 'Sexta, 14h',
              status: 'received',
            },
          ])
        } else {
          setTicket(null)
          setQuotes([])
        }
      })
      .catch(() => {})

    return () => {
      ignore = true
    }
  }, [property.id])

  async function handleApprove(providerId: string) {
    if (!ticket) return
    const updated = await approveQuote(ticket.id, providerId, ticket.run_id)
    setTicket(updated)
    // Após a aprovação o Nó 3 ainda espera a devolutiva do prestador; o hóspede só é
    // avisado quando o dia estiver confirmado.
    if (updated.status !== 'resolved' && updated.status !== 'confirmed_schedule') {
      loadTicketData()
      return
    }
    const dateStr = updated.scheduled_date || 'amanhã, 9h'
    setScheduledDate(dateStr)

    // Adiciona o aviso ao hóspede no chat do imóvel
    onNewMessage({
      id: crypto.randomUUID(),
      propertyId: property.id,
      channel: 'guest',
      sender: 'agent',
      body: `Perfeito! O anfitrião aprovou o orçamento e agendamos a visita para ${formatFriendlyDate(dateStr)}. Estaremos acompanhando!`,
      time: new Intl.DateTimeFormat('pt-BR', { hour: '2-digit', minute: '2-digit' }).format(new Date()),
      scheduledDate: dateStr,
    })
  }

  const wifiSsid = property.id === 'prop-portodigital-04' ? 'PortoDigital_Tech' : 'Zelo_Hospedes'
  const isPortoDigital = property.id === 'prop-portodigital-04'

  return (
    <div className="tab-content">
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
            property={property}
            ticket={ticket}
            quotes={quotes}
            onApprove={handleApprove}
            isLoading={loadingQuotes}
          />
          <aside style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
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

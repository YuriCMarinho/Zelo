import { useEffect, useState } from 'react'
import { approveQuote, fetchQuotes, fetchTicketsForProperty } from '../api/client'
import { ChatPanel } from './ChatPanel'
import { ProviderSimulator } from './ProviderSimulator'
import { QuotesComparison } from './QuotesComparison'
import { StateTimeline } from './StateTimeline'
import type { ChatMessage, MaintenanceTicket, Property, PropertyTab, Quote } from '../contracts'

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
        } else {
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
        }
      })
      .catch(() => {})

    return () => {
      ignore = true
    }
  }, [property.id])

  async function handleApprove(providerId: string) {
    if (!ticket) return
    const updated = await approveQuote(ticket.id, providerId)
    setTicket(updated)
    // Após a aprovação o Nó 3 ainda espera a devolutiva do prestador; o hóspede só é
    // avisado quando o dia estiver confirmado.
    if (updated.status !== 'resolved' && updated.status !== 'confirmed_schedule') return
    const dateStr = updated.scheduled_date || 'amanhã, 9h'
    setScheduledDate(dateStr)

    // Adiciona o aviso ao hóspede no chat do imóvel
    onNewMessage({
      id: crypto.randomUUID(),
      propertyId: property.id,
      channel: 'guest',
      sender: 'agent',
      body: `Perfeito! O anfitrião aprovou o orçamento e agendamos a visita para ${dateStr}. Estaremos acompanhando!`,
      time: new Intl.DateTimeFormat('pt-BR', { hour: '2-digit', minute: '2-digit' }).format(new Date()),
      scheduledDate: dateStr,
    })
  }

  return (
      <div className="tab-content">

        {tab === 'chat' && (
          <div className="split-layout">
            <ChatPanel
              property={property}
              messages={messages}
              onNewMessage={onNewMessage}
              onTicketCreated={() => loadTicketData()}
              scheduledVisit={scheduledDate}
            />
            <aside style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              <ProviderSimulator
                property={property}
                currentTicketId={ticket?.id}
                ticketStatus={ticket?.status}
                onTicketUpdated={loadTicketData}
              />
              <StateTimeline
                status={ticket?.status || 'open'}
                scheduledDate={scheduledDate}
                notifyTenant={ticket?.notify_tenant}
              />
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
              <div className="timeline-card">
                <span className="eyebrow">ÁREA DO ANFITRIÃO</span>
                <h3 style={{ margin: '4px 0' }}>Decisões com você</h3>
                <p style={{ margin: 0, fontSize: '13px', color: 'var(--mar-72)' }}>
                  Somente as decisões deste imóvel aparecem aqui. O agente reúne orçamentos e aguarda sua escolha explícita.
                </p>
              </div>
              <StateTimeline
                status={ticket?.status || 'awaiting_adm_approval'}
                scheduledDate={scheduledDate}
                notifyTenant={ticket?.notify_tenant}
              />
              <ProviderSimulator
                property={property}
                currentTicketId={ticket?.id}
                ticketStatus={ticket?.status}
                onTicketUpdated={loadTicketData}
              />
            </aside>
          </div>
        )}
      </div>
  )
}

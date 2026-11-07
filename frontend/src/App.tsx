import { useEffect, useMemo, useState } from 'react'
import {
  approveQuote,
  fetchProperties,
  fetchQuotes,
  fetchTicketsForProperty,
} from './api/client'
import { AuditPanel } from './components/AuditPanel'
import { ChatPanel } from './components/ChatPanel'
import { Header, ZeloLogo } from './components/Header'
import { ProviderSimulator } from './components/ProviderSimulator'
import { QuotesComparison } from './components/QuotesComparison'
import { StateTimeline } from './components/StateTimeline'
import type {
  ChatMessage,
  MaintenanceTicket,
  Occupancy,
  Property,
  PropertyTab,
  Quote,
} from './contracts'
import { initialMessages, properties as defaultProperties } from './demo-data'
import { parseRoute, propertyUrl, type Route } from './routes'

const money = (value: number) =>
  new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 }).format(value)

const currentMonth = new Date(new Date().getFullYear(), new Date().getMonth(), 1)

const tabs: { id: PropertyTab; label: string }[] = [
  { id: 'visao-geral', label: 'Visão geral' },
  { id: 'chat', label: 'Chat do imóvel' },
  { id: 'adm', label: 'Agente ⇄ Anfitrião' },
]

function Calendar({ occupancy }: { occupancy: readonly Occupancy[] }) {
  const [offset, setOffset] = useState(0)
  const monthDate = new Date(currentMonth.getFullYear(), currentMonth.getMonth() + offset, 1)
  const year = monthDate.getFullYear()
  const month = monthDate.getMonth()
  const totalDays = new Date(year, month + 1, 0).getDate()
  const mondayOffset = (monthDate.getDay() + 6) % 7
  const days = Array.from({ length: mondayOffset + totalDays }, (_, index) =>
    index < mondayOffset ? null : index - mondayOffset + 1
  )
  const monthLabel = new Intl.DateTimeFormat('pt-BR', { month: 'long', year: 'numeric' }).format(monthDate)

  const statusForDay = (day: number) => {
    const date = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`
    return occupancy.find((item) => date >= item.startDate && date <= item.endDate)
  }

  return (
    <section className="timeline-card" aria-label="Calendário de ocupação">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <span className="eyebrow">AGENDA DO IMÓVEL</span>
          <h3 style={{ margin: '4px 0 0' }}>Calendário de ocupação</h3>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <button
            type="button"
            className="back-btn"
            style={{ width: '32px', height: '32px' }}
            aria-label="Mês anterior"
            onClick={() => setOffset(offset - 1)}
          >
            ‹
          </button>
          <strong style={{ textTransform: 'capitalize', fontSize: '13px', minWidth: '110px', textAlign: 'center' }}>
            {monthLabel}
          </strong>
          <button
            type="button"
            className="back-btn"
            style={{ width: '32px', height: '32px' }}
            aria-label="Próximo mês"
            onClick={() => setOffset(offset + 1)}
          >
            ›
          </button>
        </div>
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(7, 1fr)',
          gap: '4px',
          textAlign: 'center',
          marginTop: '12px',
        }}
        role="grid"
        aria-label={monthLabel}
      >
        {['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom'].map((name) => (
          <span key={name} style={{ fontSize: '11px', color: 'var(--mar-72)', fontWeight: 600, paddingBottom: '6px' }} role="columnheader">
            {name}
          </span>
        ))}
        {days.map((day, index) => {
          const status = day ? statusForDay(day) : undefined
          const isToday = day === new Date().getDate() && offset === 0
          const bg =
            status?.status === 'reserved'
              ? 'var(--mar-profundo)'
              : status?.status === 'maintenance'
              ? 'var(--ambar)'
              : 'transparent'
          const color =
            status?.status === 'reserved'
              ? 'var(--areia)'
              : status?.status === 'maintenance'
              ? 'var(--mar-profundo)'
              : 'var(--mar-profundo)'

          return (
            <span
              role="gridcell"
              key={index}
              style={{
                height: '32px',
                display: 'grid',
                placeItems: 'center',
                fontSize: '12px',
                borderRadius: '8px',
                background: bg,
                color: color,
                fontWeight: status ? 700 : 500,
                outline: isToday && !status ? '1.5px solid var(--mar-profundo)' : undefined,
              }}
              aria-label={day ? `${day} de ${monthLabel}${status ? `, ${status.label}` : ', disponível'}` : undefined}
            >
              {day}
            </span>
          )
        })}
      </div>

      <div style={{ display: 'flex', gap: '16px', marginTop: '14px', fontSize: '11px', color: 'var(--mar-72)' }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <i style={{ width: '10px', height: '10px', borderRadius: '3px', background: 'var(--mar-profundo)' }} /> Reservado
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <i style={{ width: '10px', height: '10px', borderRadius: '3px', background: 'var(--ambar)' }} /> Manutenção
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <i style={{ width: '10px', height: '10px', borderRadius: '3px', border: '1px solid var(--mar-16)' }} /> Disponível
        </span>
      </div>
    </section>
  )
}

function Overview({ property }: { property: Property }) {
  return (
    <div className="split-layout">
      <div>
        <div style={{ height: '360px', borderRadius: '20px', overflow: 'hidden', border: '1px solid var(--mar-16)' }}>
          <img
            src={property.image}
            alt={property.title}
            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
          />
        </div>

        <section style={{ marginTop: '28px' }}>
          <span className="eyebrow">SOBRE O ESPAÇO</span>
          <h2 style={{ margin: '8px 0 12px', fontSize: '24px' }}>Um lugar para se sentir em casa.</h2>
          <p style={{ color: 'var(--mar-72)', lineHeight: 1.7, fontSize: '15px' }}>{property.description}</p>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
              gap: '12px',
              marginTop: '20px',
            }}
          >
            {property.amenities.map((amenity) => (
              <span key={amenity} style={{ fontSize: '13px', fontWeight: 500, color: 'var(--mar-profundo)' }}>
                ✓ {amenity}
              </span>
            ))}
          </div>
        </section>
      </div>

      <aside style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
        <div className="timeline-card">
          <span className="eyebrow">DIÁRIA & RESERVA</span>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px', margin: '8px 0' }}>
            <strong style={{ fontSize: '28px', fontWeight: 800 }}>{money(property.nightlyRate)}</strong>
            <span style={{ fontSize: '14px', color: 'var(--mar-72)' }}>/ noite</span>
          </div>
          <p style={{ margin: 0, fontSize: '13px', color: 'var(--mar-72)' }}>
            Conforto e acolhimento em cada detalhe. Gestão com Zelo do início ao fim.
          </p>
        </div>
        <Calendar occupancy={property.occupancy} />
      </aside>
    </div>
  )
}

function PropertyCard({
  property,
  navigate,
}: {
  property: Property
  navigate: (url: string) => void
}) {
  return (
    <a
      className="property-card"
      href={propertyUrl(property.id)}
      onClick={(e) => {
        e.preventDefault()
        navigate(propertyUrl(property.id))
      }}
    >
      <div className="card-img-wrap">
        <img src={property.image} alt={property.title} className="card-img" />
        <span className="card-tag">{property.tag}</span>
      </div>
      <div className="card-content">
        <div className="card-title-row">
          <h3>{property.title}</h3>
          <span className="card-rating">★ {property.rating.toFixed(2)}</span>
        </div>
        <p className="card-loc">{property.location}</p>
        <p className="card-meta">
          {property.guests} hóspedes · {property.bedrooms} quartos · {property.baths} banheiros
        </p>
        <div className="card-footer">
          <span>
            <strong>{money(property.nightlyRate)}</strong> / noite
          </span>
          <span className="card-btn">Ver imóvel ›</span>
        </div>
      </div>
    </a>
  )
}

function Listing({
  propertiesList,
  navigate,
}: {
  propertiesList: Property[]
  navigate: (url: string) => void
}) {
  const [query, setQuery] = useState('')
  const filtered = propertiesList.filter((prop) =>
    `${prop.title} ${prop.location} ${prop.neighborhood}`
      .toLowerCase()
      .includes(query.toLowerCase())
  )

  return (
    <main>
      <section className="hero">
        <div className="page-width hero-inner">
          <div>
            <span className="eyebrow">QUEBROU ALGO NO IMÓVEL? A GENTE RESOLVE. VOCÊ SÓ APROVA.</span>
            <h1>
              Gestão inteligente de estadias <br />e manutenção autônoma.
            </h1>
            <p>
              O hóspede relata, a Zelo busca orçamentos com profissionais homologados e apresenta a melhor opção.
              Nada é contratado sem sua aprovação explícita.
            </p>
            <a
              href="#imoveis"
              className="hero-cta"
              onClick={(e) => {
                e.preventDefault()
                document.getElementById('imoveis')?.scrollIntoView({ behavior: 'smooth' })
              }}
            >
              Explorar imóveis atendidos ›
            </a>
          </div>
          <div aria-hidden="true" style={{ opacity: 0.9 }}>
            <ZeloLogo size={180} />
          </div>
        </div>
      </section>

      <section id="imoveis" className="listing-section page-width">
        <div className="section-header">
          <div>
            <span className="eyebrow muted">PORTFÓLIO DE ESTADIAS</span>
            <h2>Selecione um imóvel para interagir</h2>
          </div>
          <div className="search-input-wrap">
            <span className="search-icon" aria-hidden="true">
              🔍
            </span>
            <input
              className="search-input"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Buscar por imóvel ou bairro..."
              aria-label="Buscar imóvel"
            />
          </div>
        </div>

        {filtered.length ? (
          <div className="property-grid">
            {filtered.map((property) => (
              <PropertyCard key={property.id} property={property} navigate={navigate} />
            ))}
          </div>
        ) : (
          <div style={{ padding: '48px', textAlign: 'center', background: 'var(--branco)', borderRadius: '16px' }}>
            Nenhum imóvel encontrado para “{query}”.
          </div>
        )}
      </section>
    </main>
  )
}

function PropertyPage({
  property,
  tab,
  navigate,
  messages,
  onNewMessage,
}: {
  property: Property
  tab: PropertyTab
  navigate: (url: string) => void
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
    <main className="page-width detail-page">
      <div className="breadcrumb">
        <a
          href="/"
          onClick={(e) => {
            e.preventDefault()
            navigate('/')
          }}
        >
          Imóveis
        </a>
        <span>›</span>
        <span>{property.title}</span>
      </div>

      <div className="detail-header">
        <div>
          <span className="eyebrow">{property.neighborhood.toUpperCase()} · CEARÁ</span>
          <h1>{property.title}</h1>
          <p>
            ★ {property.rating.toFixed(2)} · {property.reviews} avaliações · {property.location}
          </p>
        </div>
      </div>

      <nav className="tabs-nav" aria-label="Abas de atendimento do imóvel">
        {tabs.map((item) => (
          <a
            key={item.id}
            href={propertyUrl(property.id, item.id)}
            className={`tab-link ${tab === item.id ? 'active' : ''}`}
            aria-current={tab === item.id ? 'page' : undefined}
            onClick={(e) => {
              e.preventDefault()
              navigate(propertyUrl(property.id, item.id))
            }}
          >
            {item.label}
            {item.id === 'adm' && ticket?.status === 'awaiting_adm_approval' && (
              <span className="tab-badge" aria-hidden="true">
                Decisão pendente
              </span>
            )}
          </a>
        ))}
      </nav>

      <div className="tab-content">
        {tab === 'visao-geral' && <Overview property={property} />}

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
                onTicketUpdated={loadTicketData}
              />
            </aside>
          </div>
        )}
      </div>
    </main>
  )
}

export default function App() {
  const [route, setRoute] = useState<Route>(() => parseRoute(window.location.pathname, window.location.search))
  const [propertiesList, setPropertiesList] = useState<Property[]>(() => [...defaultProperties])
  const [messages, setMessages] = useState<ChatMessage[]>(() => [...initialMessages])

  useEffect(() => {
    fetchProperties().then(setPropertiesList).catch(() => {})
  }, [])

  useEffect(() => {
    const onPopState = () => setRoute(parseRoute(window.location.pathname, window.location.search))
    window.addEventListener('popstate', onPopState)
    return () => window.removeEventListener('popstate', onPopState)
  }, [])

  const currentProperty = useMemo(
    () => (route.view === 'property' ? propertiesList.find((p) => p.id === route.propertyId) : undefined),
    [route, propertiesList]
  )

  function navigate(url: string) {
    window.history.pushState(null, '', url)
    setRoute(parseRoute(window.location.pathname, window.location.search))
    window.scrollTo?.(0, 0)
  }

  return (
    <div className="app-shell">
      <Header navigate={navigate} activeView={route.view === 'auditoria' ? 'auditoria' : 'imoveis'} />

      {route.view === 'auditoria' ? (
        <main className="page-width detail-page">
          <div className="breadcrumb">
            <a
              href="/"
              onClick={(e) => {
                e.preventDefault()
                navigate('/')
              }}
            >
              Imóveis
            </a>
            <span>›</span>
            <span>Painel do anfitrião & Custos</span>
          </div>
          <AuditPanel />
        </main>
      ) : route.view === 'property' && currentProperty ? (
        <PropertyPage
          property={currentProperty}
          tab={route.tab}
          navigate={navigate}
          messages={messages}
          onNewMessage={(msg) => setMessages((prev) => [...prev, msg])}
        />
      ) : (
        <Listing propertiesList={propertiesList} navigate={navigate} />
      )}

      <footer className="site-footer">
        <div className="page-width footer-inner">
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <ZeloLogo size={28} />
            <span style={{ fontWeight: 800, fontSize: '18px', color: 'var(--mar-profundo)' }}>zelo</span>
            <span style={{ fontSize: '13px', color: 'var(--mar-72)' }}>
              · Quebrou algo no imóvel? A gente resolve. Você só aprova.
            </span>
          </div>
          <div>© {new Date().getFullYear()} Zelo · Estadias e Imóveis Bem Cuidados</div>
        </div>
      </footer>
    </div>
  )
}

import { useEffect, useMemo, useRef, useState } from 'react'
import type { ChatMessage, Occupancy, Property, PropertyTab } from './contracts'
import { initialMessages, properties } from './demo-data'
import { PropertyWorkspace } from './components/PropertyWorkspace'
import { AuditPanel } from './components/AuditPanel'
import { AgentGraphView } from './components/AgentGraphView'
import { fetchProperties, resetDemoData } from './api/client'
import { ManagementPage } from './management'
import { withLocalReservations } from './reservations'
import { parseRoute, propertyUrl, type Route } from './routes'

const money = (value: number) => new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 }).format(value)
const currentMonth = new Date(new Date().getFullYear(), new Date().getMonth(), 1)
const tabs: { id: PropertyTab; label: string }[] = [
  { id: 'visao-geral', label: 'Visão geral' },
  { id: 'chat', label: 'Chat do imóvel' },
  { id: 'adm', label: 'Agente ⇄ Anfitrião' },
  { id: 'orcamentos', label: 'Orçamentos' },
]

function ZeloMark({ size = 40, transparent = false }: { size?: number; transparent?: boolean }) {
  return <img className="zelo-logo" src={transparent ? '/zelo-logo-transparent.svg' : '/zelo-logo.svg'} width={size} height={size} alt="Zelo" />
}

function Header({ navigate, route }: { navigate: (url: string) => void; route: Route }) {
  const [showConfirm, setShowConfirm] = useState(false)
  const [isResetting, setIsResetting] = useState(false)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [profileMenuOpen, setProfileMenuOpen] = useState(false)
  const profileMenuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!profileMenuOpen) return
    const handleClickOutside = (event: MouseEvent) => {
      if (profileMenuRef.current && !profileMenuRef.current.contains(event.target as Node)) {
        setProfileMenuOpen(false)
      }
    }
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setProfileMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [profileMenuOpen])

  const handleReset = async () => {
    setIsResetting(true)
    try {
      await resetDemoData()
      window.location.href = '/'
    } catch {
      setShowConfirm(false)
    } finally {
      setIsResetting(false)
    }
  }

  const navItems = [
    { url: '/', label: 'Meus imóveis', view: 'listing' },
    { url: '/agentes', label: 'Grafo de Agentes', view: 'agentes' },
    { url: '/reservas', label: 'Reservas', view: 'reservas' },
    { url: '/manutencao', label: 'Manutenção', view: 'manutencao' },
    { url: '/auditoria', label: 'Auditoria', view: 'auditoria' },
  ]

  return (
    <header className="site-header">
      <div className="header-inner">
        <a href="/" className="brand" onClick={(event) => { event.preventDefault(); navigate('/') }} aria-label="Zelo, ir para imóveis">
          <ZeloMark /><span>zelo<small>QUEBROU? A GENTE RESOLVE.</small></span>
        </a>
        <nav className="header-nav desktop-nav" aria-label="Navegação principal">
          {navItems.map((item) => (
            <a
              key={item.url}
              href={item.url}
              aria-current={route.view === item.view || (route.view === 'property' && item.view === 'listing') ? 'page' : undefined}
              onClick={(event) => { event.preventDefault(); navigate(item.url) }}
            >
              {item.label}
            </a>
          ))}
        </nav>
        <div className="header-right">
          <button
            type="button"
            className="demo-reset-btn"
            onClick={() => setShowConfirm(true)}
            title="Reinicializar ambiente de demonstração"
          >
            ↻ Resetar Demo
          </button>
          <div className="profile-menu-container" ref={profileMenuRef}>
            <button
              type="button"
              className={`avatar-btn ${profileMenuOpen ? 'open' : ''}`}
              onClick={() => setProfileMenuOpen((prev) => !prev)}
              aria-label="Perfil do anfitrião"
              aria-expanded={profileMenuOpen}
              aria-haspopup="menu"
            >
              <span className="avatar" aria-hidden="true">A</span>
            </button>
            {profileMenuOpen && (
              <div className="profile-dropdown" role="menu" aria-label="Opções do perfil">
                <div className="profile-dropdown-header">
                  <span className="avatar avatar-sm" aria-hidden="true">A</span>
                  <div className="profile-dropdown-user">
                    <strong>Anfitrião</strong>
                    <span>anfitriao@zelo.app</span>
                  </div>
                </div>
                <div className="profile-dropdown-divider" />
                <button
                  type="button"
                  role="menuitem"
                  className={`profile-dropdown-item ${route.view === 'configuracoes' ? 'active' : ''}`}
                  onClick={() => {
                    setProfileMenuOpen(false)
                    navigate('/configuracoes')
                  }}
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/>
                    <circle cx="12" cy="12" r="3"/>
                  </svg>
                  <span>Configurações</span>
                </button>
              </div>
            )}
          </div>
          <button
            type="button"
            className={`mobile-menu-btn ${mobileMenuOpen ? 'open' : ''}`}
            onClick={() => setMobileMenuOpen((prev) => !prev)}
            aria-label={mobileMenuOpen ? 'Fechar menu de navegação' : 'Abrir menu de navegação'}
            aria-expanded={mobileMenuOpen}
          >
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden="true">
              {mobileMenuOpen ? (
                <>
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </>
              ) : (
                <>
                  <line x1="4" y1="6" x2="20" y2="6" />
                  <line x1="4" y1="12" x2="20" y2="12" />
                  <line x1="4" y1="18" x2="20" y2="18" />
                </>
              )}
            </svg>
          </button>
        </div>
      </div>
      {mobileMenuOpen && (
        <nav className="mobile-nav-drawer page-width" aria-label="Navegação mobile">
          {navItems.map((item) => (
            <a
              key={item.url}
              href={item.url}
              aria-current={route.view === item.view || (route.view === 'property' && item.view === 'listing') ? 'page' : undefined}
              onClick={(event) => {
                event.preventDefault()
                setMobileMenuOpen(false)
                navigate(item.url)
              }}
            >
              {item.label}
            </a>
          ))}
        </nav>
      )}
      {showConfirm && (
        <div className="demo-reset-modal-overlay" role="dialog" aria-modal="true">
          <div className="demo-reset-modal">
            <h3>Resetar Dados da Demonstração?</h3>
            <p>
              Isso restaurará os 3 imóveis originais, limpará chamados transacionais e reiniciará o
              ledger para que os avaliadores possam testar do zero.
            </p>
            <div className="demo-reset-actions">
              <button
                type="button"
                className="action-secondary"
                onClick={() => setShowConfirm(false)}
                disabled={isResetting}
              >
                Cancelar
              </button>
              <button
                type="button"
                className="action-primary"
                onClick={handleReset}
                disabled={isResetting}
              >
                {isResetting ? 'Reinicializando...' : 'Confirmar Reset'}
              </button>
            </div>
          </div>
        </div>
      )}
    </header>
  )
}

function PropertyCard({ property, navigate }: { property: Property; navigate: (url: string) => void }) {
  return <a className="property-card" href={propertyUrl(property.id)} onClick={(event) => { event.preventDefault(); navigate(propertyUrl(property.id)) }}>
    <div className="card-image-wrap"><img src={property.image} alt={property.title} className="card-image" /><span className="card-tag">{property.tag}</span></div>
    <div className="card-body"><div className="card-title-row"><h3>{property.title}</h3><span className="rating">★ <strong>{property.rating.toFixed(2)}</strong></span></div>
      <p className="card-location">{property.location}</p><p className="card-meta">{property.guests} hóspedes · {property.bedrooms} quartos · {property.baths} banheiros</p>
      <div className="card-footer"><span><strong>{money(property.nightlyRate)}</strong> <span>/ noite</span></span><span className="card-arrow" aria-hidden="true">↗</span></div>
    </div>
  </a>
}

function Listing({ navigate, propertiesList }: { navigate: (url: string) => void; propertiesList: Property[] }) {
  const [query, setQuery] = useState('')
  const filtered = propertiesList.filter((property) => `${property.title} ${property.location}`.toLocaleLowerCase('pt-BR').includes(query.toLocaleLowerCase('pt-BR')))
  return (
    <main>
      <section className="hero">
        <div className="hero-inner">
          <div>
            <span className="eyebrow light">CUIDADO EM CADA DETALHE</span>
            <h1>Seu imóvel bem cuidado.<br />Você no controle.</h1>
            <p>Conversas, manutenção e decisões reunidas em um só lugar. A gente resolve; você aprova.</p>
            <a href="#imoveis" className="hero-button">Ver meus imóveis <span aria-hidden="true">↗</span></a>
          </div>
          <div className="hero-emblem" aria-hidden="true">
            <ZeloMark size={180} transparent />
          </div>
        </div>
      </section>
      <section id="imoveis" className="listing-section page-width"><div className="section-heading"><div><span className="eyebrow">SEUS ESPAÇOS</span><h2>Meus imóveis</h2><p>Acompanhe cada estadia com tranquilidade.</p></div><label className="search-box"><span aria-hidden="true">⌕</span><span className="sr-only">Buscar imóvel</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Buscar imóvel ou local" /></label></div>
      {filtered.length ? (
        <div className="property-grid">
          {filtered.map((property) => (
            <PropertyCard key={property.id} property={property} navigate={navigate} />
          ))}
        </div>
      ) : (
        <div className="empty-state">Nenhum imóvel encontrado para “{query}”.</div>
      )}
      </section>
    </main>
  )
}

function Calendar({ occupancy }: { occupancy: readonly Occupancy[] }) {
  const [offset, setOffset] = useState(0)
  const monthDate = new Date(currentMonth.getFullYear(), currentMonth.getMonth() + offset, 1)
  const year = monthDate.getFullYear()
  const month = monthDate.getMonth()
  const totalDays = new Date(year, month + 1, 0).getDate()
  const mondayOffset = (monthDate.getDay() + 6) % 7
  const days = Array.from({ length: mondayOffset + totalDays }, (_, index) => index < mondayOffset ? null : index - mondayOffset + 1)
  const monthLabel = new Intl.DateTimeFormat('pt-BR', { month: 'long', year: 'numeric' }).format(monthDate)
  const statusForDay = (day: number) => {
    const date = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`
    return occupancy.find((item) => date >= item.startDate && date <= item.endDate)
  }
  return <section className="calendar-card" aria-label="Calendário de ocupação"><div className="calendar-header"><div><span className="eyebrow">AGENDA DO IMÓVEL</span><h3>Calendário de ocupação</h3></div><div className="calendar-controls"><button aria-label="Mês anterior" onClick={() => setOffset(offset - 1)}>‹</button><strong>{monthLabel}</strong><button aria-label="Próximo mês" onClick={() => setOffset(offset + 1)}>›</button></div></div>
    <div className="calendar-grid" role="grid" aria-label={monthLabel}>{['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom'].map((name) => <span key={name} className="calendar-weekday" role="columnheader">{name}</span>)}{days.map((day, index) => { const status = day ? statusForDay(day) : undefined; return <span role="gridcell" key={index} className={`calendar-day ${status ? `day-${status.status}` : ''} ${day === new Date().getDate() && offset === 0 ? 'day-today' : ''}`} aria-label={day ? `${day} de ${monthLabel}${status ? `, ${status.label}` : ', disponível'}` : undefined} title={status?.label}>{day}</span> })}</div>
    <div className="calendar-legend"><span><i className="legend-available" /> Disponível</span><span><i className="legend-reserved" /> Reservado</span><span><i className="legend-maintenance" /> Manutenção</span></div>
  </section>
}

function Overview({ property, navigate }: { property: Property; navigate: (url: string) => void }) {
  return (
    <div className="overview-grid">
      <div>
        <div className="gallery">
          <img className="gallery-main" src={property.image} alt={`Vista principal de ${property.title}`} />
          <div>
            {property.gallery.map((image, index) => (
              <img key={image} src={image} alt={`Ambiente ${index + 1} de ${property.title}`} />
            ))}
          </div>
        </div>
        <section className="about-section">
          <h2>Sobre o imóvel</h2>
          <p>{property.description}</p>
          <div className="amenities">
            {property.amenities.map((amenity) => (
              <span key={amenity}>{amenity}</span>
            ))}
          </div>
        </section>
      </div>
      <aside className="overview-aside">
        <div className="stay-card">
          <div className="tabular-nums">
            <strong>{money(property.nightlyRate)}</strong>
            <span> / noite</span>
          </div>
          <p>Canal direto com triagem automática de dúvidas de reserva e chamados de manutenção.</p>
          <div className="stay-divider" />
          <span>Ponto único de chat por imóvel</span>
          <span>Contratação somente com aprovação do anfitrião</span>
          <button
            type="button"
            className="shortcut-btn primary"
            style={{ marginTop: '8px', textAlign: 'center' }}
            onClick={() => navigate(propertyUrl(property.id, 'chat'))}
          >
            Abrir chat do imóvel →
          </button>
        </div>
        <Calendar occupancy={property.occupancy} />
      </aside>
    </div>
  )
}

const sampleQuotes = [
  { id: 'carlos', name: 'Carlos Eletricista', rating: '4,9 · 128 avaliações', price: 180, when: 'Amanhã, 9h', note: 'Recomendado' },
  { id: 'volt', name: 'Volt Reparos', rating: '4,7 · 64 avaliações', price: 240, when: 'Hoje, 17h', note: '' },
  { id: 'joao', name: 'João Faz-Tudo', rating: '4,5 · 21 avaliações', price: 150, when: 'Sexta, 14h', note: '' },
] as const

function QuotesPanel({ property, navigate }: { property: Property; navigate: (url: string) => void }) {
  const [selected, setSelected] = useState<string>('carlos')
  const [confirmed, setConfirmed] = useState(false)
  const choice = sampleQuotes.find((quote) => quote.id === selected) ?? sampleQuotes[0]
  return (
    <section className="quotes-layout" aria-labelledby="quotes-heading">
      <div className="quotes-main">
        <div
          style={{
            background: 'var(--mar-08)',
            padding: '12px 16px',
            borderRadius: '12px',
            marginBottom: '16px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            gap: '12px',
          }}
        >
          <span>
            Simulação rápida de comparativo. Para aprovar chamados reais dos agentes, acesse{' '}
            <strong>Agente ⇄ Anfitrião</strong>.
          </span>
          <button
            type="button"
            className="action-primary"
            style={{ padding: '6px 14px', fontSize: '12px', whiteSpace: 'nowrap' }}
            onClick={() => navigate(propertyUrl(property.id, 'adm'))}
          >
            Ir para Agente ⇄ Anfitrião ↗
          </button>
        </div>
        <div className="quotes-intro">
          <span className="status-pill">{confirmed ? 'Escolha simulada' : 'Aguardando sua decisão'}</span>
          <h2 id="quotes-heading">Chuveiro sem água quente</h2>
          <p>3 de 5 eletricistas consultados enviaram orçamento. O hóspede já foi informado do acompanhamento.</p>
        </div>
        <div className="quote-list" role="radiogroup" aria-label="Escolha um orçamento">
          {sampleQuotes.map((quote) => (
            <button
              type="button"
              role="radio"
              aria-checked={selected === quote.id}
              key={quote.id}
              className={`quote-card ${selected === quote.id ? 'selected' : ''}`}
              onClick={() => {
                setSelected(quote.id)
                setConfirmed(false)
              }}
            >
              <span className="quote-card-top">
                <span>
                  <strong>{quote.name}</strong>
                  <small>
                    {quote.rating}
                    {quote.note ? ` · ${quote.note}` : ''}
                  </small>
                </span>
                <b className="tabular-nums">{money(quote.price)}</b>
              </span>
              <span className="quote-time">{quote.when}</span>
            </button>
          ))}
        </div>
        <div className="quote-action">
          <button type="button" onClick={() => setConfirmed(true)}>
            {confirmed ? 'Simulação concluída' : `Escolher ${choice.name} · ${money(choice.price)}`}
          </button>
          <p>Simulação local: nenhuma contratação ou agendamento é realizado.</p>
        </div>
      </div>
      <aside className="quotes-aside">
        <h3>Como funciona a aprovação</h3>
        <p>O Nó 3 coleta cotações sem negociar preço e pausa até sua escolha explícita antes de agendar a visita.</p>
        <div className="quote-steps">
          <span>
            1. <strong>Orçamentos recebidos</strong>
          </span>
          <span>
            2. <strong>Sua aprovação</strong>
          </span>
          <span>
            3. <strong>Agendamento na janela ideal</strong>
          </span>
        </div>
      </aside>
    </section>
  )
}

function getPropertyState(property: Property): string {
  const loc = `${property.location} ${property.neighborhood} ${property.id}`.toLowerCase()
  if (loc.includes('recife') || loc.includes('pernambuco') || loc.includes('portodigital')) return 'PERNAMBUCO'
  if (loc.includes('rio de janeiro') || loc.includes('copacabana')) return 'RIO DE JANEIRO'
  if (loc.includes('são paulo') || loc.includes('sao paulo') || loc.includes('madalena')) return 'SÃO PAULO'
  if (loc.includes('gramado') || loc.includes('serra gaúcha') || loc.includes('gaucha')) return 'RIO GRANDE DO SUL'
  if (loc.includes('ceará') || loc.includes('ceara') || loc.includes('cumbuco') || loc.includes('fortaleza')) return 'CEARÁ'
  return ''
}

function PropertyPage({
  property,
  tab,
  navigate,
  messages,
  sendMessage,
}: {
  property: Property
  tab: PropertyTab
  navigate: (url: string) => void
  messages: ChatMessage[]
  sendMessage: (message: ChatMessage) => void
}) {
  const stateName = getPropertyState(property)
  return (
    <main className="page-width detail-page">
      <div className="breadcrumb" style={{ justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <a
            href="/"
            onClick={(event) => {
              event.preventDefault()
              navigate('/')
            }}
          >
            Imóveis
          </a>
          <span>›</span>
          <span>{property.title}</span>
        </div>
        <a
          href="/agentes"
          style={{ fontSize: '13px', fontWeight: 600, color: 'var(--mar-profundo)' }}
          onClick={(event) => {
            event.preventDefault()
            navigate('/agentes')
          }}
        >
          Ver fluxo no Grafo de Agentes →
        </a>
      </div>
      <div className="detail-intro">
        <div>
          <span className="eyebrow">
            {property.neighborhood.toLocaleUpperCase('pt-BR')}{stateName ? ` · ${stateName}` : ''}
          </span>
          <h1>{property.title}</h1>
          <p className="tabular-nums">
            <span className="rating">★ {property.rating.toFixed(2)}</span> <span className="dot-sep">·</span>{' '}
            {property.reviews} avaliações <span className="dot-sep">·</span> {property.location}
          </p>
        </div>
        <div className="detail-capacity tabular-nums">
          {property.guests} hóspedes <span>·</span> {property.bedrooms} quartos <span>·</span> {property.beds} camas{' '}
          <span>·</span> {property.baths} banheiros
        </div>
      </div>
      <nav className="tabs" aria-label="Seções do imóvel">
        {tabs.map((item) => (
          <a
            key={item.id}
            href={propertyUrl(property.id, item.id)}
            aria-current={tab === item.id ? 'page' : undefined}
            className={tab === item.id ? 'active' : ''}
            onClick={(event) => {
              event.preventDefault()
              navigate(propertyUrl(property.id, item.id))
            }}
          >
            {item.label}
          </a>
        ))}
      </nav>
      <div className="tab-content" key={property.id}>
        {tab === 'visao-geral' ? (
          <Overview property={property} navigate={navigate} />
        ) : tab === 'orcamentos' ? (
          <QuotesPanel property={property} navigate={navigate} />
        ) : (
          <PropertyWorkspace property={property} tab={tab} messages={messages} onNewMessage={sendMessage} />
        )}
      </div>
    </main>
  )
}

export default function App() {
  const [route, setRoute] = useState<Route>(() => parseRoute(window.location.pathname, window.location.search))
  const [propertiesList, setPropertiesList] = useState<Property[]>(() => [...properties])
  useEffect(() => { fetchProperties().then(setPropertiesList).catch(() => {}) }, [])
  const [messages, setMessages] = useState<ChatMessage[]>(() => [...initialMessages])
  useEffect(() => { const onPopState = () => setRoute(parseRoute(window.location.pathname, window.location.search)); window.addEventListener('popstate', onPopState); return () => window.removeEventListener('popstate', onPopState) }, [])
  const property = useMemo(() => route.view === 'property' ? propertiesList.find((item) => item.id === route.propertyId) : undefined, [route, propertiesList])
  function navigate(url: string) { window.history.pushState(null, '', url); setRoute(parseRoute(window.location.pathname, window.location.search)); window.scrollTo?.(0, 0) }
  return (
    <div className="app-shell">
      <Header navigate={navigate} route={route} />
      {route.view === 'auditoria' ? (
        <main className="page-width detail-page">
          <AuditPanel />
        </main>
      ) : route.view === 'agentes' ? (
        <main className="page-width detail-page">
          <AgentGraphView navigate={navigate} propertiesList={propertiesList} />
        </main>
      ) : route.view === 'property' && property ? (
        <PropertyPage
          property={withLocalReservations(property)}
          tab={route.tab}
          navigate={navigate}
          messages={messages}
          sendMessage={(message) => setMessages((previous) => [...previous, message])}
        />
      ) : route.view === 'reservas' || route.view === 'manutencao' || route.view === 'configuracoes' ? (
        <ManagementPage key={route.view} view={route.view} navigate={navigate} />
      ) : (
        <Listing navigate={navigate} propertiesList={propertiesList} />
      )}
      <footer className="site-footer">
        <div className="page-width footer-inner">
          <div className="footer-brand">
            <ZeloMark size={28} />
          </div>
          <span className="footer-tagline">Quebrou algo no imóvel? A gente resolve. Você só aprova.</span>
          <span className="footer-copy">© {new Date().getFullYear()} Zelo</span>
        </div>
      </footer>
    </div>
  )
}

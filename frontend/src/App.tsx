import { useEffect, useMemo, useState } from 'react'
import type { ChatMessage, Occupancy, Property, PropertyTab } from './contracts'
import { initialMessages, properties } from './demo-data'
import { PropertyWorkspace } from './components/PropertyWorkspace'
import { AuditPanel } from './components/AuditPanel'
import { fetchProperties } from './api/client'
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
  return <header className="site-header">
    <div className="header-inner">
      <a href="/" className="brand" onClick={(event) => { event.preventDefault(); navigate('/') }} aria-label="Zelo, ir para imóveis">
        <ZeloMark /><span>zelo<small>QUEBROU? A GENTE RESOLVE.</small></span>
      </a>
      <nav className="header-nav" aria-label="Navegação principal">{[{ url: '/', label: 'Meus imóveis', view: 'listing' }, { url: '/reservas', label: 'Reservas', view: 'reservas' }, { url: '/manutencao', label: 'Manutenção', view: 'manutencao' }, { url: '/configuracoes', label: 'Configurações', view: 'configuracoes' }, { url: '/auditoria', label: 'Auditoria', view: 'auditoria' }].map((item) => <a key={item.url} href={item.url} aria-current={route.view === item.view || (route.view === 'property' && item.view === 'listing') ? 'page' : undefined} onClick={(event) => { event.preventDefault(); navigate(item.url) }}>{item.label}</a>)}</nav>
      <div className="header-right"><div className="avatar" aria-label="Perfil do anfitrião">A</div></div>
    </div>
  </header>
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
  return <main>
    <section className="hero"><div className="hero-inner"><div><span className="eyebrow light">CUIDADO EM CADA DETALHE</span><h1>Seu imóvel bem cuidado.<br />Você no controle.</h1><p>Conversas, manutenção e decisões reunidas em um só lugar. A gente resolve; você aprova.</p><a href="#imoveis" className="hero-button">Ver meus imóveis <span aria-hidden="true">↗</span></a></div><div className="hero-emblem" aria-hidden="true"><ZeloMark size={180} transparent /></div></div></section>
    <section id="imoveis" className="listing-section page-width"><div className="section-heading"><div><span className="eyebrow">SEUS ESPAÇOS</span><h2>Meus imóveis</h2><p>Acompanhe cada estadia com tranquilidade.</p></div><label className="search-box"><span aria-hidden="true">⌕</span><span className="sr-only">Buscar imóvel</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Buscar imóvel ou local" /></label></div>
      {filtered.length ? <div className="property-grid">{filtered.map((property) => <PropertyCard key={property.id} property={property} navigate={navigate} />)}</div> : <div className="empty-state">Nenhum imóvel encontrado para “{query}”.</div>}
      <div className="care-banner"><div className="care-symbol"><ZeloMark size={32} /></div><div><strong>Cuidar bem é estar por perto.</strong><p>Conversas, agenda e manutenção conectadas a cada imóvel.</p></div></div>
    </section>
  </main>
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

function Overview({ property }: { property: Property }) {
  return <div className="overview-grid"><div><div className="gallery"><img className="gallery-main" src={property.image} alt={`Vista principal de ${property.title}`} /><div>{property.gallery.map((image, index) => <img key={image} src={image} alt={`Ambiente ${index + 1} de ${property.title}`} />)}</div></div><section className="about-section"><span className="eyebrow">SOBRE O ESPAÇO</span><h2>Um lugar para se sentir em casa.</h2><p>{property.description}</p><div className="amenities">{property.amenities.map((amenity) => <span key={amenity}>✓ {amenity}</span>)}</div></section></div><aside className="overview-aside"><div className="stay-card"><span className="eyebrow">SUA PRÓXIMA ESTADIA</span><div><strong>{money(property.nightlyRate)}</strong><span> / noite</span></div><p>Conforto em cada detalhe, cuidado em cada conversa.</p><div className="stay-divider" /><span>◷ &nbsp; Check-in flexível</span><span>✦ &nbsp; Suporte durante a estadia</span></div><Calendar occupancy={property.occupancy} /></aside></div>
}

const sampleQuotes = [
  { id: 'carlos', name: 'Carlos Eletricista', rating: '4,9 · 128 avaliações', price: 180, when: 'Amanhã, 9h', note: 'Recomendado' },
  { id: 'volt', name: 'Volt Reparos', rating: '4,7 · 64 avaliações', price: 240, when: 'Hoje, 17h', note: '' },
  { id: 'joao', name: 'João Faz-Tudo', rating: '4,5 · 21 avaliações', price: 150, when: 'Sexta, 14h', note: '' },
] as const

function QuotesPanel({ property }: { property: Property }) {
  const [selected, setSelected] = useState<string>('carlos')
  const [confirmed, setConfirmed] = useState(false)
  const choice = sampleQuotes.find((quote) => quote.id === selected) ?? sampleQuotes[0]
  return <section className="quotes-layout" aria-labelledby="quotes-heading"><div className="quotes-main"><div className="quotes-intro"><span className="status-pill">{confirmed ? 'Escolha simulada' : 'Aguardando sua decisão'}</span><span className="eyebrow">EXEMPLO DE COMPARATIVO · {property.title.toLocaleUpperCase('pt-BR')}</span><h2 id="quotes-heading">Chuveiro sem água quente</h2><p>Neste exemplo, 3 de 5 eletricistas responderam. O hóspede foi avisado de que o problema está sendo cuidado.</p></div><div className="quote-list" role="radiogroup" aria-label="Escolha um orçamento">{sampleQuotes.map((quote) => <button type="button" role="radio" aria-checked={selected === quote.id} key={quote.id} className={`quote-card ${selected === quote.id ? 'selected' : ''}`} onClick={() => { setSelected(quote.id); setConfirmed(false) }}><span className="quote-card-top"><span><strong>{quote.name}</strong><small>{quote.rating}{quote.note ? ` · ${quote.note}` : ''}</small></span><b>{money(quote.price)}</b></span><span className="quote-time">{quote.when}</span></button>)}</div><div className="quote-action"><button type="button" onClick={() => setConfirmed(true)}>{confirmed ? 'Simulação concluída' : `Escolher ${choice.name} · ${money(choice.price)}`}</button><p>Simulação local: nenhuma contratação ou agendamento é realizado.</p></div></div><aside className="quotes-aside"><span className="eyebrow">VOCÊ DECIDE</span><h3>Compare com calma.</h3><p>Preço, avaliação e horário ficam lado a lado para ajudar sua escolha. A contratação só pode acontecer após sua aprovação.</p><div className="quote-steps"><span>01 <strong>Orçamentos recebidos</strong></span><span>02 <strong>Sua escolha</strong></span><span>03 <strong>Agendamento confirmado</strong></span></div></aside></section>
}

function PropertyPage({ property, tab, navigate, messages, sendMessage }: { property: Property; tab: PropertyTab; navigate: (url: string) => void; messages: ChatMessage[]; sendMessage: (message: ChatMessage) => void }) {
  return <main className="page-width detail-page"><div className="breadcrumb"><a href="/" onClick={(event) => { event.preventDefault(); navigate('/') }}>Imóveis</a><span>›</span><span>{property.title}</span></div><div className="detail-intro"><div><span className="eyebrow">{property.neighborhood.toLocaleUpperCase('pt-BR')} · CEARÁ</span><h1>{property.title}</h1><p><span className="rating">★ {property.rating.toFixed(2)}</span> <span className="dot-sep">·</span> {property.reviews} avaliações <span className="dot-sep">·</span> {property.location}</p></div><div className="detail-capacity">{property.guests} hóspedes <span>·</span> {property.bedrooms} quartos <span>·</span> {property.beds} camas <span>·</span> {property.baths} banheiros</div></div><nav className="tabs" aria-label="Seções do imóvel">{tabs.map((item) => <a key={item.id} href={propertyUrl(property.id, item.id)} aria-current={tab === item.id ? 'page' : undefined} className={tab === item.id ? 'active' : ''} onClick={(event) => { event.preventDefault(); navigate(propertyUrl(property.id, item.id)) }}>{item.label}</a>)}</nav><div className="tab-content" key={`${property.id}-${tab}`}>{tab === 'visao-geral' ? <Overview property={property} /> : tab === 'orcamentos' ? <QuotesPanel property={property} /> : <PropertyWorkspace property={property} tab={tab} messages={messages} onNewMessage={sendMessage} />}</div></main>
}

export default function App() {
  const [route, setRoute] = useState<Route>(() => parseRoute(window.location.pathname, window.location.search))
  const [propertiesList, setPropertiesList] = useState<Property[]>(() => [...properties])
  useEffect(() => { fetchProperties().then(setPropertiesList).catch(() => {}) }, [])
  const [messages, setMessages] = useState<ChatMessage[]>(() => [...initialMessages])
  useEffect(() => { const onPopState = () => setRoute(parseRoute(window.location.pathname, window.location.search)); window.addEventListener('popstate', onPopState); return () => window.removeEventListener('popstate', onPopState) }, [])
  const property = useMemo(() => route.view === 'property' ? propertiesList.find((item) => item.id === route.propertyId) : undefined, [route, propertiesList])
  function navigate(url: string) { window.history.pushState(null, '', url); setRoute(parseRoute(window.location.pathname, window.location.search)); window.scrollTo?.(0, 0) }
  return <div className="app-shell"><Header navigate={navigate} route={route} />{route.view === 'auditoria' ? <main className="page-width detail-page"><AuditPanel /></main> : route.view === 'property' && property ? <PropertyPage property={withLocalReservations(property)} tab={route.tab} navigate={navigate} messages={messages} sendMessage={(message) => setMessages((previous) => [...previous, message])} /> : route.view === 'reservas' || route.view === 'manutencao' || route.view === 'configuracoes' ? <ManagementPage key={route.view} view={route.view} navigate={navigate} /> : <Listing navigate={navigate} propertiesList={propertiesList} />}<footer className="site-footer"><div className="page-width"><ZeloMark size={32} /><span>Quebrou algo no imóvel? A gente resolve. Você só aprova.</span><span>© {new Date().getFullYear()} Zelo</span></div></footer></div>
}

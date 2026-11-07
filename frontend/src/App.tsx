import { useEffect, useMemo, useState, type FormEvent } from 'react'
import type { ChatMessage, ChatRole, Occupancy, Property, PropertyTab } from './contracts'
import { demoBudget, initialMessages, properties } from './demo-data'
import { parseRoute, propertyUrl, type Route } from './routes'

const money = (value: number) => new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 }).format(value)
const usd = (value: number) => new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'USD' }).format(value)
const currentMonth = new Date(new Date().getFullYear(), new Date().getMonth(), 1)
const tabs: { id: PropertyTab; label: string }[] = [
  { id: 'visao-geral', label: 'Visão geral' },
  { id: 'chat', label: 'Chat do imóvel' },
  { id: 'adm', label: 'Agente ⇄ Anfitrião' },
]

function BudgetMonitor() {
  const percent = Math.min(100, (demoBudget.spentUsd / demoBudget.totalUsd) * 100)
  return <div className="budget-monitor" aria-label={`Orçamento de demonstração: ${usd(demoBudget.spentUsd)} de ${usd(demoBudget.totalUsd)} utilizados`}>
    <div className="budget-icon" aria-hidden="true">◔</div>
    <div className="budget-copy"><strong>Orçamento IA</strong><span>{usd(demoBudget.spentUsd)} / {usd(demoBudget.totalUsd)}</span></div>
    <div className="budget-meter" role="progressbar" aria-valuenow={demoBudget.spentUsd} aria-valuemin={0} aria-valuemax={demoBudget.totalUsd} aria-label="Consumo do orçamento"><span style={{ width: `${percent}%` }} /></div>
    <span className="budget-status">Modo simulado</span>
  </div>
}

function Header({ navigate }: { navigate: (url: string) => void }) {
  return <header className="site-header">
    <div className="header-inner">
      <a href="/" className="brand" onClick={(event) => { event.preventDefault(); navigate('/') }} aria-label="SmartRepair, ir para imóveis">
        <span className="brand-symbol" aria-hidden="true"><span /></span><span>smart<span className="brand-accent">repair</span><small>ESTADIAS BEM CUIDADAS</small></span>
      </a>
      <nav className="header-nav" aria-label="Navegação principal"><a href="/" onClick={(event) => { event.preventDefault(); navigate('/') }}>Explorar imóveis</a><span className="nav-divider" /><span className="nav-label">Painel do anfitrião</span></nav>
      <div className="header-right"><BudgetMonitor /><div className="avatar" aria-label="Perfil do anfitrião">A</div></div>
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

function Listing({ navigate }: { navigate: (url: string) => void }) {
  const [query, setQuery] = useState('')
  const filtered = properties.filter((property) => `${property.title} ${property.location}`.toLocaleLowerCase('pt-BR').includes(query.toLocaleLowerCase('pt-BR')))
  return <main>
    <section className="hero"><div className="hero-inner"><div><span className="eyebrow light">SEUS ESPAÇOS, NOSSO CUIDADO</span><h1>Hospedar bem começa<br />com cada detalhe.</h1><p>Encontre seus imóveis, acompanhe a ocupação e cuide de cada estadia em um só lugar.</p><a href="#imoveis" className="hero-button">Explorar imóveis <span aria-hidden="true">↗</span></a></div><div className="hero-shape" aria-hidden="true"><span>✦</span></div></div></section>
    <section id="imoveis" className="listing-section page-width"><div className="section-heading"><div><span className="eyebrow">PORTFÓLIO DE ESTADIAS</span><h2>Explore nossos imóveis</h2><p>Espaços únicos para momentos que merecem atenção.</p></div><label className="search-box"><span aria-hidden="true">⌕</span><span className="sr-only">Buscar imóvel</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Buscar por imóvel ou local" /></label></div>
      {filtered.length ? <div className="property-grid">{filtered.map((property) => <PropertyCard key={property.id} property={property} navigate={navigate} />)}</div> : <div className="empty-state">Nenhum imóvel encontrado para “{query}”.</div>}
      <div className="care-banner"><div className="care-symbol">✳</div><div><strong>Mais tranquilidade para quem hospeda.</strong><p>Conversas, agenda e manutenção conectadas a cada imóvel.</p></div><span aria-hidden="true">↗</span></div>
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

function MessageList({ messages }: { messages: ChatMessage[] }) {
  return <div className="message-list" aria-live="polite">{messages.map((message) => <div className={`message-row ${message.sender === 'agent' ? 'agent' : 'person'}`} key={message.id}><div className="message-avatar" aria-hidden="true">{message.sender === 'agent' ? '✦' : message.sender === 'anfitriao' ? 'A' : message.sender === 'camareira' ? 'C' : 'H'}</div><div><span className="message-name">{message.sender === 'agent' ? 'Assistente SmartRepair' : message.sender === 'anfitriao' ? 'Anfitrião' : message.sender === 'camareira' ? 'Camareira' : 'Hóspede'} <time>{message.time}</time></span><div className="message-bubble">{message.body}</div></div></div>)}</div>
}

function ChatPanel({ property, channel, messages, sendMessage }: { property: Property; channel: 'guest' | 'admin'; messages: ChatMessage[]; sendMessage: (message: ChatMessage) => void }) {
  const [role, setRole] = useState<ChatRole>('hospede')
  const [draft, setDraft] = useState('')
  const admin = channel === 'admin'
  const visible = messages.filter((message) => message.propertyId === property.id && message.channel === channel)
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const body = draft.trim()
    if (!body) return
    sendMessage({ id: crypto.randomUUID(), propertyId: property.id, channel, sender: admin ? 'anfitriao' : role, body, time: new Intl.DateTimeFormat('pt-BR', { hour: '2-digit', minute: '2-digit' }).format(new Date()) })
    setDraft('')
  }
  return <div className="workspace-grid"><section className="conversation-card"><div className="conversation-header"><div className="conversation-avatar">✦</div><div><span className="eyebrow">{admin ? 'CANAL PRIVATIVO · ADM' : 'PONTO ÚNICO DE CHAT'}</span><h2>{admin ? 'Agente ⇄ Anfitrião' : `Converse sobre ${property.title}`}</h2><p>{admin ? 'Decisões e atualizações de manutenção deste imóvel.' : 'Dúvidas sobre a estadia ou relatos de manutenção.'}</p></div><span className="online-dot" title="Demonstração local" /></div>
    {!admin && <div className="role-bar"><span>Estou falando como</span><div className="segmented"><button type="button" className={role === 'hospede' ? 'selected' : ''} aria-pressed={role === 'hospede'} onClick={() => setRole('hospede')}>Hóspede</button><button type="button" className={role === 'camareira' ? 'selected' : ''} aria-pressed={role === 'camareira'} onClick={() => setRole('camareira')}>Camareira</button></div></div>}
    <MessageList messages={visible} /><form className="message-form" onSubmit={submit}><label className="sr-only" htmlFor="message-input">Mensagem</label><input id="message-input" value={draft} onChange={(event) => setDraft(event.target.value)} maxLength={1500} placeholder={admin ? 'Escreva para o agente...' : 'Escreva sua mensagem...'} /><button type="submit" disabled={!draft.trim()} aria-label="Enviar mensagem">➤</button></form><p className="demo-note">Demonstração local · mensagens sem envio ao backend</p></section>
    <aside className="workspace-aside"><div className="info-card"><span className="eyebrow">{admin ? 'ÁREA DO ANFITRIÃO' : 'COMO FUNCIONA'}</span><h3>{admin ? 'Decisões com você.' : 'Um canal para tudo.'}</h3><p>{admin ? 'O agente reúne orçamentos e aguarda sua escolha explícita antes de qualquer contratação.' : 'Perguntas de reserva seguem para o atendimento. Problemas no imóvel seguem para a triagem de manutenção.'}</p><div className="info-steps">{(admin ? ['Receba orçamentos', 'Escolha um prestador', 'Acompanhe o agendamento'] : ['Envie sua mensagem', 'O assunto é identificado', 'A equipe acompanha']).map((step, index) => <div key={step}><span>{String(index + 1).padStart(2, '0')}</span>{step}</div>)}</div></div><div className="privacy-card"><span>♧</span><div><strong>{admin ? 'Sessão exclusiva' : 'Conversa por imóvel'}</strong><p>{admin ? 'Somente as decisões deste imóvel aparecem aqui.' : 'As mensagens ficam associadas a este imóvel.'}</p></div></div></aside></div>
}

function PropertyPage({ property, tab, navigate, messages, sendMessage }: { property: Property; tab: PropertyTab; navigate: (url: string) => void; messages: ChatMessage[]; sendMessage: (message: ChatMessage) => void }) {
  return <main className="page-width detail-page"><div className="breadcrumb"><a href="/" onClick={(event) => { event.preventDefault(); navigate('/') }}>Imóveis</a><span>›</span><span>{property.title}</span></div><div className="detail-intro"><div><span className="eyebrow">{property.neighborhood.toLocaleUpperCase('pt-BR')} · CEARÁ</span><h1>{property.title}</h1><p><span className="rating">★ {property.rating.toFixed(2)}</span> <span className="dot-sep">·</span> {property.reviews} avaliações <span className="dot-sep">·</span> {property.location}</p></div><div className="detail-capacity">{property.guests} hóspedes <span>·</span> {property.bedrooms} quartos <span>·</span> {property.beds} camas <span>·</span> {property.baths} banheiros</div></div><nav className="tabs" aria-label="Seções do imóvel">{tabs.map((item) => <a key={item.id} href={propertyUrl(property.id, item.id)} aria-current={tab === item.id ? 'page' : undefined} className={tab === item.id ? 'active' : ''} onClick={(event) => { event.preventDefault(); navigate(propertyUrl(property.id, item.id)) }}>{item.label}</a>)}</nav><div className="tab-content" key={`${property.id}-${tab}`}>{tab === 'visao-geral' ? <Overview property={property} /> : <ChatPanel property={property} channel={tab === 'adm' ? 'admin' : 'guest'} messages={messages} sendMessage={sendMessage} />}</div></main>
}

export default function App() {
  const [route, setRoute] = useState<Route>(() => parseRoute(window.location.pathname, window.location.search))
  const [messages, setMessages] = useState<ChatMessage[]>(() => [...initialMessages])
  useEffect(() => { const onPopState = () => setRoute(parseRoute(window.location.pathname, window.location.search)); window.addEventListener('popstate', onPopState); return () => window.removeEventListener('popstate', onPopState) }, [])
  const property = useMemo(() => route.view === 'property' ? properties.find((item) => item.id === route.propertyId) : undefined, [route])
  function navigate(url: string) { window.history.pushState(null, '', url); setRoute(parseRoute(window.location.pathname, window.location.search)); window.scrollTo?.(0, 0) }
  return <div className="app-shell"><Header navigate={navigate} />{route.view === 'property' && property ? <PropertyPage property={property} tab={route.tab} navigate={navigate} messages={messages} sendMessage={(message) => setMessages((previous) => [...previous, message])} /> : <Listing navigate={navigate} />}<footer className="site-footer"><div className="page-width"><span>✦ smartrepair</span><span>Estadias bem cuidadas, do início ao fim.</span><span>© {new Date().getFullYear()} SmartRepair</span></div></footer></div>
}

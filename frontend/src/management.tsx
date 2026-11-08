import { useState, type FormEvent } from 'react'
import { properties } from './demo-data'
import { propertyUrl } from './routes'
import type { Reservation } from './reservations'

export type ManagementView = 'reservas' | 'manutencao' | 'configuracoes'
const dateLabel = (date: string) => new Intl.DateTimeFormat('pt-BR').format(new Date(`${date}T12:00:00`))
const today = new Date()
const day = (offset: number) => { const date = new Date(today.getFullYear(), today.getMonth(), today.getDate() + offset); return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}` }
interface Ticket { id: string; propertyId: string; title: string; detail: string; priority: string; status: number }
interface Settings { name: string; email: string; reservations: boolean; maintenance: boolean }
const initialReservations: Reservation[] = [
  { id: 'res-1', propertyId: properties[0]!.id, guest: 'Marina Oliveira', start: properties[0]!.occupancy[0]!.startDate, end: properties[0]!.occupancy[0]!.endDate, guests: 2 },
  { id: 'res-2', propertyId: properties[1]!.id, guest: 'Lucas Santos', start: properties[1]!.occupancy[0]!.startDate, end: properties[1]!.occupancy[0]!.endDate, guests: 2 },
]
const initialTickets: Ticket[] = [
  { id: 'ticket-1', propertyId: properties[0]!.id, title: 'Chuveiro sem água quente', detail: 'Verificar a resistência do chuveiro da suíte.', priority: 'Alta', status: 0 },
  { id: 'ticket-2', propertyId: properties[1]!.id, title: 'Revisão do ar-condicionado', detail: 'Limpeza dos filtros e revisão preventiva.', priority: 'Normal', status: 1 },
]
const stages = ['Aberto', 'Em andamento', 'Concluído']

function useSavedState<T>(key: string, initial: T) {
  const [value, setValue] = useState<T>(() => {
    try { const saved = localStorage.getItem(key); return saved ? JSON.parse(saved) as T : initial } catch { return initial }
  })
  const [storageError, setStorageError] = useState('')
  function save(next: T) {
    setValue(next)
    try { localStorage.setItem(key, JSON.stringify(next)); setStorageError('') } catch { setStorageError('Não foi possível salvar neste navegador. As alterações ficam disponíveis apenas nesta sessão.') }
  }
  return [value, save, storageError] as const
}

function PropertySelect({ value, onChange, all = false }: { value: string; onChange: (value: string) => void; all?: boolean }) {
  return <select value={value} onChange={(event) => onChange(event.target.value)}>{all && <option value="">Todos os imóveis</option>}{properties.map((property) => <option key={property.id} value={property.id}>{property.title}</option>)}</select>
}

function Reservations({ navigate }: { navigate: (url: string) => void }) {
  const [items, save, storageError] = useSavedState('zelo-reservations-v1', initialReservations)
  const [filter, setFilter] = useState('')
  const [query, setQuery] = useState('')
  const [creating, setCreating] = useState(false)
  const [propertyId, setPropertyId] = useState(properties[0]!.id)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const visible = items.filter((item) => (!filter || item.propertyId === filter) && item.guest.toLocaleLowerCase('pt-BR').includes(query.toLocaleLowerCase('pt-BR'))).sort((a, b) => a.start.localeCompare(b.start))
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    const guest = String(data.get('guest') ?? '').trim()
    const start = String(data.get('start'))
    const end = String(data.get('end'))
    const guests = Number(data.get('guests'))
    const property = properties.find((item) => item.id === propertyId)!
    if (!guest) { setError('Informe o nome do hóspede.'); return }
    if (end <= start) { setError('O check-out deve ser posterior ao check-in.'); return }
    if (guests < 1 || guests > property.guests) { setError(`Este imóvel recebe até ${property.guests} hóspedes.`); return }
    if (items.some((item) => item.propertyId === propertyId && start < item.end && end > item.start) || property.occupancy.some((item) => start <= item.endDate && end > item.startDate)) { setError('Este período já possui uma reserva ou manutenção. Escolha outras datas.'); return }
    save([...items, { id: crypto.randomUUID(), propertyId, guest, start, end, guests }])
    setCreating(false); setError(''); setNotice('Reserva adicionada à demonstração local.')
  }
  return <><div className="management-toolbar"><div className="management-filters"><label>Imóvel<PropertySelect value={filter} onChange={setFilter} all /></label><label>Hóspede<input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Buscar pelo nome" /></label></div><button className="action-primary" onClick={() => { setCreating(!creating); setError(''); setNotice('') }}>{creating ? 'Fechar formulário' : '+ Nova reserva'}</button></div>
    {creating && <form className="management-card management-form" onSubmit={submit}><h2>Nova reserva</h2><div className="form-grid"><label>Imóvel<PropertySelect value={propertyId} onChange={setPropertyId} /></label><label>Nome do hóspede<input name="guest" required maxLength={100} /></label><label>Check-in<input type="date" name="start" min={day(0)} required /></label><label>Check-out<input type="date" name="end" min={day(1)} required /></label><label>Hóspedes<input type="number" name="guests" min="1" max={properties.find((item) => item.id === propertyId)!.guests} defaultValue="1" required /></label></div>{error && <p className="form-error" role="alert">{error}</p>}<button className="action-primary">Salvar reserva</button></form>}
    <p role="status">{notice}</p>{storageError && <p role="alert" className="form-error">{storageError}</p>}
    <div className="management-results"><span>{visible.length} reserva(s)</span></div><div className="reservation-list">{visible.map((item) => { const property = properties.find((entry) => entry.id === item.propertyId)!; return <article className="management-card reservation-row" key={item.id}><img src={property.image} alt={property.title} /><div><span className="eyebrow">{property.title}</span><h2>{item.guest}</h2><p>{dateLabel(item.start)} → {dateLabel(item.end)} · {item.guests} hóspede(s)</p></div><span className="management-badge">{item.end <= day(0) ? 'Finalizada' : item.start <= day(0) ? 'Em estadia' : 'Confirmada'}</span><a className="action-secondary" href={propertyUrl(property.id)} onClick={(event) => { event.preventDefault(); navigate(propertyUrl(property.id)) }}>Ver imóvel ↗</a></article> })}</div>{!visible.length && <div className="management-card empty-state"><h2>Nenhuma reserva encontrada</h2><p>Tente outro nome ou imóvel.</p><button className="action-secondary" onClick={() => { setFilter(''); setQuery('') }}>Limpar filtros</button></div>}</>
}

function Maintenance() {
  const [items, save, storageError] = useSavedState('zelo-tickets-v1', initialTickets)
  const [filter, setFilter] = useState('')
  const [status, setStatus] = useState('')
  const [creating, setCreating] = useState(false)
  const [propertyId, setPropertyId] = useState(properties[0]!.id)
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')
  const visible = items.filter((item) => (!filter || item.propertyId === filter) && (status === '' || item.status === Number(status)))
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    const title = String(data.get('title') ?? '').trim()
    const detail = String(data.get('detail') ?? '').trim()
    if (!title || !detail) { setError('Preencha o assunto e a descrição do chamado.'); return }
    save([{ id: crypto.randomUUID(), propertyId, title, detail, priority: String(data.get('priority')), status: 0 }, ...items]); setCreating(false); setError(''); setNotice('Chamado criado na demonstração local.')
  }
  return <><div className="management-stats">{stages.map((stage, index) => <div className="management-card" key={stage}><span>{stage}</span><strong>{items.filter((item) => item.status === index).length}</strong></div>)}</div><div className="management-toolbar"><div className="management-filters"><label>Imóvel<PropertySelect value={filter} onChange={setFilter} all /></label><label>Status<select value={status} onChange={(event) => setStatus(event.target.value)}><option value="">Todos os status</option>{stages.map((stage, index) => <option value={index} key={stage}>{stage}</option>)}</select></label></div><button className="action-primary" onClick={() => { setCreating(!creating); setError('') }}>{creating ? 'Fechar formulário' : '+ Novo chamado'}</button></div>
    {creating && <form className="management-card management-form" onSubmit={submit}><h2>Novo chamado</h2><div className="form-grid"><label>Imóvel<PropertySelect value={propertyId} onChange={setPropertyId} /></label><label>Prioridade<select name="priority"><option>Normal</option><option>Alta</option></select></label><label className="form-full">Assunto<input name="title" required maxLength={100} /></label><label className="form-full">Descrição<textarea name="detail" required maxLength={1500} rows={3} /></label></div>{error && <p role="alert" className="form-error">{error}</p>}<button className="action-primary">Criar chamado</button></form>}
    <p role="status">{notice}</p>{storageError && <p role="alert" className="form-error">{storageError}</p>}<div className="ticket-grid">{visible.map((item) => <article className="management-card ticket-card" key={item.id}><div className="ticket-top"><span className="eyebrow">{properties.find((property) => property.id === item.propertyId)?.title}</span><span className={`management-badge ${item.priority === 'Alta' ? 'priority-high' : ''}`}>Prioridade {item.priority.toLowerCase()}</span></div><h2>{item.title}</h2><p>{item.detail}</p><ol className="ticket-progress" aria-label="Andamento do chamado">{stages.map((stage, index) => <li key={stage} className={index <= item.status ? 'reached' : ''} aria-current={index === item.status ? 'step' : undefined}>{stage}</li>)}</ol>{item.status < 2 ? <button className="action-secondary" onClick={() => { save(items.map((entry) => entry.id === item.id ? { ...entry, status: entry.status + 1 } : entry)); setNotice(`“${item.title}”: ${stages[item.status + 1]}.`) }}>{item.status === 0 ? 'Iniciar atendimento' : 'Marcar como concluído'}</button> : <span className="completed-note">✓ Atendimento concluído</span>}</article>)}</div>{!visible.length && <div className="management-card empty-state"><h2>Nenhum chamado por aqui</h2><p>Altere os filtros para ver outros atendimentos.</p><button className="action-secondary" onClick={() => { setFilter(''); setStatus('') }}>Limpar filtros</button></div>}</>
}

function Preferences() {
  const [saved, save, storageError] = useSavedState<Settings>('zelo-settings-v1', { name: 'Anfitrião', email: '', reservations: true, maintenance: true })
  const [draft, setDraft] = useState(saved)
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!draft.name.trim()) { setError('Informe seu nome.'); return }
    save({ ...draft, name: draft.name.trim(), email: draft.email.trim() }); setError(''); setNotice('Preferências salvas neste navegador.')
  }
  return <form className="settings-layout" onSubmit={submit}><section className="management-card management-form"><span className="eyebrow">SEU PERFIL</span><h2>Como podemos chamar você?</h2><div className="form-grid"><label>Nome<input required maxLength={100} value={draft.name} onChange={(event) => { setDraft({ ...draft, name: event.target.value }); setNotice('') }} /></label><label>E-mail<input type="email" value={draft.email} onChange={(event) => { setDraft({ ...draft, email: event.target.value }); setNotice('') }} placeholder="voce@exemplo.com" /></label></div><h2>Preferências de notificações</h2><p>Escolha quais atualizações deseja acompanhar.</p><label className="preference-row"><span><strong>Reservas e estadias</strong><small>Novas reservas e movimentações de hóspedes.</small></span><input type="checkbox" checked={draft.reservations} onChange={(event) => { setDraft({ ...draft, reservations: event.target.checked }); setNotice('') }} /></label><label className="preference-row"><span><strong>Chamados de manutenção</strong><small>Atualizações de atendimento dos seus imóveis.</small></span><input type="checkbox" checked={draft.maintenance} onChange={(event) => { setDraft({ ...draft, maintenance: event.target.checked }); setNotice('') }} /></label>{error && <p role="alert" className="form-error">{error}</p>}<div className="settings-actions"><button className="action-primary">Salvar preferências</button><button className="action-secondary" type="button" onClick={() => { setDraft(saved); setNotice('Alterações desfeitas.'); setError('') }}>Desfazer alterações</button></div><p role="status">{notice}</p>{storageError && <p role="alert" className="form-error">{storageError}</p>}</section><aside className="management-card settings-note"><span className="eyebrow">DO SEU JEITO</span><h2>Você escolhe o que acompanhar.</h2><p>Suas preferências ficam guardadas neste navegador. Nesta demonstração, nenhum e-mail ou notificação é enviado.</p></aside></form>
}

export function ManagementPage({ view, navigate }: { view: ManagementView; navigate: (url: string) => void }) {
  const content = { reservas: ['SUAS ESTADIAS', 'Reservas', 'Organize chegadas, partidas e os próximos dias dos seus imóveis.'], manutencao: ['CUIDADO CONTÍNUO', 'Manutenção', 'Do primeiro relato ao problema resolvido, acompanhe cada atendimento.'], configuracoes: ['SEU ESPAÇO', 'Configurações', 'Ajuste seu perfil e as atualizações que fazem sentido para você.'] }[view]
  return <main className="page-width management-page"><div className="management-heading"><span className="eyebrow">{content[0]}</span><h1>{content[1]}</h1><p>{content[2]}</p></div><p className="management-demo">Demonstração local · dados salvos apenas neste navegador</p>{view === 'reservas' ? <Reservations navigate={navigate} /> : view === 'manutencao' ? <Maintenance /> : <Preferences />}</main>
}

import type { ManagementView } from './management'
import type { PropertyTab } from './contracts'
import { properties } from './demo-data'

export type Route =
  | { view: 'listing' }
  | { view: 'auditoria' }
  | { view: 'agentes' }
  | { view: ManagementView }
  | { view: 'property'; propertyId: string; tab: PropertyTab }

export function parseRoute(pathname: string, search: string): Route {
  if (pathname === '/auditoria') return { view: 'auditoria' }
  const page = pathname.replace(/\/$/, '')
  if (page === '/agentes' || page === '/grafo') return { view: 'agentes' }
  if (page === '/reservas') return { view: 'reservas' }
  if (page === '/manutencao') return { view: 'manutencao' }
  if (page === '/configuracoes') return { view: 'configuracoes' }
  const match = /^\/imoveis\/([^/]+)\/?$/.exec(pathname)
  if (!match?.[1] || !properties.some((property) => property.id === match[1])) return { view: 'listing' }
  const requested = new URLSearchParams(search).get('aba')
  const tab: PropertyTab = requested === 'chat' || requested === 'adm' || requested === 'orcamentos' ? requested : 'visao-geral'
  return { view: 'property', propertyId: match[1], tab }
}

export function propertyUrl(id: string, tab: PropertyTab = 'visao-geral') {
  return `/imoveis/${id}${tab === 'visao-geral' ? '' : `?aba=${tab}`}`
}

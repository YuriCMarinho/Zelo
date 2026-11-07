import type { PropertyTab } from './contracts'
import { properties } from './demo-data'

export type Route = { view: 'listing' } | { view: 'property'; propertyId: string; tab: PropertyTab }

export function parseRoute(pathname: string, search: string): Route {
  const match = /^\/imoveis\/([^/]+)\/?$/.exec(pathname)
  if (!match?.[1] || !properties.some((property) => property.id === match[1])) return { view: 'listing' }
  const requested = new URLSearchParams(search).get('aba')
  const tab: PropertyTab = requested === 'chat' || requested === 'adm' || requested === 'orcamentos' ? requested : 'visao-geral'
  return { view: 'property', propertyId: match[1], tab }
}

export function propertyUrl(id: string, tab: PropertyTab = 'visao-geral') {
  return `/imoveis/${id}${tab === 'visao-geral' ? '' : `?aba=${tab}`}`
}

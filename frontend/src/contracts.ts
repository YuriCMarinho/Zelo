export type PropertyId = string
export type ChatRole = 'hospede' | 'camareira'
export type PropertyTab = 'visao-geral' | 'chat' | 'adm' | 'orcamentos'
export type OccupancyStatus = 'reserved' | 'maintenance'

export interface Occupancy {
  startDate: string
  endDate: string
  status: OccupancyStatus
  label: string
}

export interface Property {
  id: PropertyId
  title: string
  location: string
  neighborhood: string
  description: string
  image: string
  gallery: readonly string[]
  nightlyRate: number
  guests: number
  bedrooms: number
  beds: number
  baths: number
  rating: number
  reviews: number
  amenities: readonly string[]
  occupancy: readonly Occupancy[]
  tag: string
}

export interface ChatMessage {
  id: string
  propertyId: PropertyId
  channel: 'guest' | 'admin'
  sender: 'agent' | 'hospede' | 'camareira' | 'anfitriao'
  body: string
  time: string
}

export interface BudgetSnapshot {
  spentUsd: number
  totalUsd: number
  reservedUsd: number
  mode: 'mock' | 'live'
}

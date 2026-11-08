export type PropertyId = string
export type ChatRole = 'hospede' | 'camareira'
export type PropertyTab = 'visao-geral' | 'chat' | 'adm' | 'auditoria' | 'orcamentos'
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
  channel: 'guest' | 'cleaner' | 'admin'
  sender: 'agent' | 'hospede' | 'camareira' | 'anfitriao'
  body: string
  time: string
  ticketId?: string | null
  bookingId?: string | null
  scheduledDate?: string | null
  suggestedActions?: string[]
}

export interface BookingItem {
  id: string
  property_id: string
  guest_name: string
  guest_contact: string
  start_date: string
  end_date: string
  status: 'pending_approval' | 'confirmed' | 'active' | 'rejected' | 'cancelled' | string
  total_price?: number | null
  num_guests?: number
  rejection_reason?: string | null
  session_id?: string | null
  notes?: string | null
  created_at: string
}

export interface MaintenanceTicket {
  id: string
  run_id: string
  property_id: string
  reported_by_role: string
  category: string
  urgency: 'urgent' | 'normal'
  location_in_property: string
  description: string
  status: string
  selected_provider_id?: string | null
  scheduled_date?: string | null
  notify_tenant: boolean
  adm_synthesis?: string | null
  created_at: string
  updated_at?: string | null
}

export function formatFriendlyDate(val: string | null | undefined): string {
  if (!val) return ''
  if (typeof val === 'string' && val.includes('-') && (val.includes('T') || val.includes(' '))) {
    const d = new Date(val)
    if (!isNaN(d.getTime())) {
      const weekdays = ['Domingo', 'Segunda-feira', 'Terça-feira', 'Quarta-feira', 'Quinta-feira', 'Sexta-feira', 'Sábado']
      const months = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']
      const day = String(d.getUTCDate()).padStart(2, '0')
      const month = months[d.getUTCMonth()]
      const weekday = weekdays[d.getUTCDay()]
      const hours = String(d.getUTCHours()).padStart(2, '0')
      const mins = String(d.getUTCMinutes()).padStart(2, '0')
      return `${weekday}, ${day} de ${month} às ${hours}:${mins}`
    }
  }
  return val
}

export interface Quote {
  id: string
  ticket_id: string
  run_id: string
  provider_id: string
  provider_name?: string | null
  provider_rating?: number | null
  amount: number | null
  description?: string | null
  proposed_availability?: string | null
  status: string
  is_recommended?: boolean
}

export interface CostSummary {
  total_cost_usd: number
  total_input_tokens: number
  total_output_tokens: number
  total_calls: number
  by_node: Record<string, number>
  by_model: Record<string, number>
  budget_limit_usd: number
  percentage_used: number
  alert_triggered?: string | null
}

export interface AuditEvent {
  id: string
  created_at: string
  run_id: string
  ticket_id?: string | null
  node: string
  event_type: string
  payload: Record<string, unknown>
}

export interface BudgetSnapshot {
  spentUsd: number
  totalUsd: number
  reservedUsd: number
  mode: 'mock' | 'live'
}

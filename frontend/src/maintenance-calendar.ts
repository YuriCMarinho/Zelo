import { formatFriendlyDate, type MaintenanceTicket, type Occupancy } from './contracts'

export function maintenanceOccupancy(tickets: MaintenanceTicket[], propertyId: string): Occupancy[] {
  return tickets.flatMap((ticket) => {
    if (ticket.property_id !== propertyId || !ticket.scheduled_date ||
      !['confirmed_schedule', 'notifying_tenant', 'resolved'].includes(ticket.status)) return []
    const date = ticket.scheduled_date.slice(0, 10)
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || !Number.isFinite(Date.parse(ticket.scheduled_date))) return []
    return [{
      startDate: date,
      endDate: date,
      status: 'maintenance' as const,
      label: `Visita de manutenção · ${formatFriendlyDate(ticket.scheduled_date)} · ${ticket.description}`,
    }]
  })
}

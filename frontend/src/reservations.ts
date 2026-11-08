import type { Property } from './contracts'

export interface Reservation {
  id: string
  propertyId: string
  guest: string
  start: string
  end: string
  guests: number
}

export function withLocalReservations(property: Property): Property {
  try {
    const saved: unknown = JSON.parse(localStorage.getItem('zelo-reservations-v1') ?? '[]')
    if (!Array.isArray(saved)) return property
    const occupancy = saved.filter((item): item is Reservation =>
      item?.propertyId === property.id && typeof item.start === 'string' && typeof item.end === 'string' && typeof item.guest === 'string',
    ).flatMap((item) => {
      const lastNight = new Date(`${item.end}T12:00:00`)
      if (!Number.isFinite(lastNight.getTime())) return []
      lastNight.setDate(lastNight.getDate() - 1)
      const endDate = `${lastNight.getFullYear()}-${String(lastNight.getMonth() + 1).padStart(2, '0')}-${String(lastNight.getDate()).padStart(2, '0')}`
      return [{ startDate: item.start, endDate, status: 'reserved' as const, label: `Reserva de ${item.guest}` }]
    })
    return { ...property, occupancy: [...property.occupancy, ...occupancy] }
  } catch {
    return property
  }
}

import type { ChatMessage, Property } from './contracts'

const today = new Date()
const month = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}`
const day = (value: number) => `${month}-${String(value).padStart(2, '0')}`

export const properties: readonly Property[] = [
  {
    id: 'casa-aurora',
    title: 'Casa Aurora',
    location: 'Praia do Futuro, Fortaleza',
    neighborhood: 'Praia do Futuro',
    description: 'Acorde com a brisa do mar em uma casa iluminada, feita para dias sem pressa. A varanda, a piscina e os espaços amplos acolhem toda a família.',
    image: 'https://images.unsplash.com/photo-1499793983690-e29da59ef1c2?w=1400&q=85',
    gallery: [
      'https://images.unsplash.com/photo-1613490493576-7fde63acd811?w=900&q=85',
      'https://images.unsplash.com/photo-1600607687920-4e2a09cf159d?w=900&q=85',
    ],
    nightlyRate: 590, guests: 8, bedrooms: 3, beds: 5, baths: 2, rating: 4.92, reviews: 86,
    amenities: ['Piscina privativa', 'Wi-Fi rápido', 'Ar-condicionado', 'Cozinha equipada'],
    occupancy: [
      { startDate: day(5), endDate: day(9), status: 'reserved', label: 'Reserva confirmada' },
      { startDate: day(17), endDate: day(20), status: 'reserved', label: 'Reserva confirmada' },
      { startDate: day(24), endDate: day(24), status: 'maintenance', label: 'Manutenção prevista' },
    ],
    tag: 'Perto do mar',
  },
  {
    id: 'loft-jardim',
    title: 'Loft Jardim',
    location: 'Meireles, Fortaleza',
    neighborhood: 'Meireles',
    description: 'Um refúgio contemporâneo no coração da cidade. Cafés, restaurantes e a orla ficam a poucos passos do seu próximo endereço.',
    image: 'https://images.unsplash.com/photo-1600210492486-724fe5c67fb0?w=1400&q=85',
    gallery: [
      'https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?w=900&q=85',
      'https://images.unsplash.com/photo-1600566753190-17f0baa2a6c3?w=900&q=85',
    ],
    nightlyRate: 340, guests: 3, bedrooms: 1, beds: 2, baths: 1, rating: 4.88, reviews: 124,
    amenities: ['Wi-Fi rápido', 'Espaço de trabalho', 'Ar-condicionado', 'Check-in autônomo'],
    occupancy: [
      { startDate: day(2), endDate: day(6), status: 'reserved', label: 'Reserva confirmada' },
      { startDate: day(14), endDate: day(16), status: 'reserved', label: 'Reserva confirmada' },
    ],
    tag: 'No coração da cidade',
  },
  {
    id: 'vila-areia',
    title: 'Vila Areia',
    location: 'Cumbuco, Ceará',
    neighborhood: 'Cumbuco',
    description: 'Pés na areia e uma atmosfera tranquila para reunir quem você ama. Um lugar para aproveitar o sol e a simplicidade dos melhores dias.',
    image: 'https://images.unsplash.com/photo-1520250497591-112f2f40a3f4?w=1400&q=85',
    gallery: [
      'https://images.unsplash.com/photo-1571896349842-33c89424de2d?w=900&q=85',
      'https://images.unsplash.com/photo-1600566753086-00f18fb6b3ea?w=900&q=85',
    ],
    nightlyRate: 720, guests: 10, bedrooms: 4, beds: 7, baths: 3, rating: 4.96, reviews: 58,
    amenities: ['Acesso à praia', 'Piscina', 'Estacionamento', 'Cozinha equipada'],
    occupancy: [
      { startDate: day(8), endDate: day(13), status: 'reserved', label: 'Reserva confirmada' },
      { startDate: day(22), endDate: day(27), status: 'reserved', label: 'Reserva confirmada' },
    ],
    tag: 'Refúgio à beira-mar',
  },
  {
    id: 'prop-portodigital-04',
    title: 'Studio Tech Porto Digital',
    location: 'Cais do Apolo, 222 - Bairro do Recife, Recife',
    neighborhood: 'Recife Antigo',
    description: 'Studio contemporâneo no coração do Porto Digital, a passos do Marco Zero e dos armazéns criativos. Workstation com monitor externo, internet fibra 500Mbps, ar-condicionado inverter silencioso e vista para o Rio Capibaribe. Perfeito para hackathons, nômades digitais e fins de semana no polo de inovação.',
    image: 'https://images.unsplash.com/photo-1522071820081-009f0129c71c?w=1400&q=85',
    gallery: [
      'https://images.unsplash.com/photo-1497366216548-37526070297c?w=900&q=85',
      'https://images.unsplash.com/photo-1517502884422-41eaead166d4?w=900&q=85',
    ],
    nightlyRate: 280, guests: 2, bedrooms: 1, beds: 1, baths: 1, rating: 4.98, reviews: 94,
    amenities: ['Wi-Fi 500Mbps dedicado', 'Workstation ergonômica', 'Ar-condicionado Inverter', 'Fechadura 24h autônoma', 'Copa Gourmet', 'Vista Capibaribe'],
    occupancy: [
      { startDate: day(5), endDate: day(8), status: 'reserved', label: 'Imersão Tech Reserva' },
      { startDate: day(18), endDate: day(21), status: 'reserved', label: 'Hackathon Weekend' },
    ],
    tag: 'Porto Digital · Recife',
  },
]

export const initialMessages: readonly ChatMessage[] = [
  { id: 'welcome-casa', propertyId: 'casa-aurora', channel: 'guest', sender: 'agent', body: 'Olá! Sou a assistente da Casa Aurora. Posso ajudar com dúvidas sobre a estadia ou receber um relato de manutenção. Como posso ajudar?', time: '09:41' },
  { id: 'welcome-loft', propertyId: 'loft-jardim', channel: 'guest', sender: 'agent', body: 'Olá! Bem-vindo ao Loft Jardim. Conte comigo para dúvidas sobre o espaço ou para relatar algum problema.', time: '09:41' },
  { id: 'welcome-vila', propertyId: 'vila-areia', channel: 'guest', sender: 'agent', body: 'Olá! Sou a assistente da Vila Areia. Como posso ajudar com sua estadia?', time: '09:41' },
  { id: 'welcome-recife', propertyId: 'prop-portodigital-04', channel: 'guest', sender: 'agent', body: 'Olá! Bem-vindo ao Studio Tech Porto Digital no Bairro do Recife! Como posso ajudar com sua estadia, internet de alta velocidade ou comodidades no polo de inovação?', time: '09:41' },
  { id: 'adm-casa', propertyId: 'casa-aurora', channel: 'admin', sender: 'agent', body: 'Olá, anfitrião! Esta é a sessão reservada para decisões sobre manutenção da Casa Aurora. Novos orçamentos e pedidos de aprovação aparecerão aqui.', time: '09:42' },
  { id: 'adm-loft', propertyId: 'loft-jardim', channel: 'admin', sender: 'agent', body: 'Olá, anfitrião! Esta sessão acompanha os tickets e as decisões de manutenção do Loft Jardim.', time: '09:42' },
  { id: 'adm-vila', propertyId: 'vila-areia', channel: 'admin', sender: 'agent', body: 'Olá, anfitrião! Esta sessão acompanha os tickets e as decisões de manutenção da Vila Areia.', time: '09:42' },
  { id: 'adm-recife', propertyId: 'prop-portodigital-04', channel: 'admin', sender: 'agent', body: 'Olá, anfitrião! Esta é a sessão para acompanhar o Studio Tech Porto Digital. Decisões de manutenção e cotações com prestadores locais do Recife Antigo aparecerão aqui.', time: '09:42' },
]

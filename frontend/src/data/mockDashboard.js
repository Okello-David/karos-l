export const occupancy = {
  occupied: 98,
  total: 120,
  available: 22,
}

export const outstandingPayments = {
  occupantsOwing: 12,
  totalBalance: 1850000,
}

export const properties = [
  { id: 1, name: 'Karos', totalSpaces: 40, occupied: 38, occupancyRate: 95 },
  { id: 2, name: 'Upper Karos', totalSpaces: 60, occupied: 42, occupancyRate: 70 },
  { id: 3, name: 'Lion Cottage', totalSpaces: 20, occupied: 18, occupancyRate: 90 },
]

export const recentPayments = [
  { id: 1, occupant: 'Sarah Nakato', amount: 150000, date: '25 Jun 2026', property: 'Lion Cottage' },
  { id: 2, occupant: 'Grace Akello', amount: 200000, date: '24 Jun 2026', property: 'Upper Karos' },
  { id: 3, occupant: 'Peter Mwangi', amount: 180000, date: '23 Jun 2026', property: 'Karos' },
  { id: 4, occupant: 'Faith Atuhaire', amount: 150000, date: '22 Jun 2026', property: 'Lion Cottage' },
  { id: 5, occupant: 'Daniel Ochieng', amount: 200000, date: '21 Jun 2026', property: 'Upper Karos' },
]

export const recentActivity = [
  { id: 1, type: 'checkin', actor: 'David Kimani', detail: 'checked into', target: 'Lion Cottage', time: '2 hours ago' },
  { id: 2, type: 'payment', actor: 'Sarah Nakato', detail: 'paid', target: 'UGX 150,000', time: '3 hours ago' },
  { id: 3, type: 'checkout', actor: 'John Okello', detail: 'checked out of', target: 'Upper Karos', time: '5 hours ago' },
  { id: 4, type: 'payment', actor: 'Grace Akello', detail: 'paid', target: 'UGX 200,000', time: '1 day ago' },
  { id: 5, type: 'checkin', actor: 'Peter Mwangi', detail: 'checked into', target: 'Karos', time: '1 day ago' },
  { id: 6, type: 'payment', actor: 'Faith Atuhaire', detail: 'paid', target: 'UGX 150,000', time: '2 days ago' },
]

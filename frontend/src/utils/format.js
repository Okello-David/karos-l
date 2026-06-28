export function formatUGX(amount) {
  return 'UGX ' + amount.toLocaleString('en-UG')
}

export function formatPhone(phone) {
  if (!phone) return '—'
  return phone
}

export function fullName(first, last) {
  return `${first} ${last}`.trim()
}

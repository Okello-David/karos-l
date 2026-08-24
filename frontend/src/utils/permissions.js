// UI-only permission helpers. Backend authorization is authoritative (see
// docs/ARCHITECTURE_DECISIONS.md) — these exist purely to hide actions a user
// can't perform, improving UX. Never rely on these for security.

export function isSuperAdmin(user) {
  return Boolean(user?.is_superuser)
}

export function isPropertyManager(user) {
  return Boolean(user?.is_superuser) || Boolean(user?.groups?.includes('Property Manager'))
}

// Property Manager and above can create/modify business data (occupants,
// occupancy, payments, properties/sections/units). A plain authenticated
// ("Staff") user cannot.
export function canManageBusinessData(user) {
  return isPropertyManager(user)
}

// User-account management (Administration → Users) requires Super Admin —
// a Property Manager must never see this, since it includes resetting any
// account's password.
export function canManageUsers(user) {
  return isSuperAdmin(user)
}

import { api } from './api'

const TOKEN_KEY = 'auth_token'
const USER_KEY = 'auth_user'

export const authService = {
  async login(username, password) {
    const data = await api.post('/auth/login/', { username, password })
    localStorage.setItem(TOKEN_KEY, data.token)
    localStorage.setItem(USER_KEY, JSON.stringify(data.user))
    return data.user
  },

  async logout() {
    try {
      await api.post('/auth/logout/')
    } catch {
      // Token may already be invalid/expired server-side; clear local state regardless.
    }
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
  },

  isAuthenticated() {
    return Boolean(localStorage.getItem(TOKEN_KEY))
  },

  getUser() {
    const raw = localStorage.getItem(USER_KEY)
    return raw ? JSON.parse(raw) : null
  },

  clearSession() {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
  },
}

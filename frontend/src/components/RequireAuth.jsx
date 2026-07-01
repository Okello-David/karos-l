import { Navigate, useLocation } from 'react-router-dom'
import { authService } from '../services/auth'

export default function RequireAuth({ children }) {
  const location = useLocation()

  if (!authService.isAuthenticated()) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return children
}

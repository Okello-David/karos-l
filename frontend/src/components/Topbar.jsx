import { useMemo } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import Breadcrumb from './Breadcrumb'
import { authService } from '../services/auth'

const staticBreadcrumbMap = {
  '/': [{ label: 'Overview' }],
  '/explorer': [{ label: 'Explorer' }],
  '/properties': [{ label: 'Properties' }],
  '/occupants': [{ label: 'Occupants' }],
  '/occupants/new': [{ label: 'Occupants', path: '/occupants' }, { label: 'New Occupant' }],
  '/payments': [{ label: 'Payments' }],
  '/receipts': [{ label: 'Receipts' }],
  '/reports': [{ label: 'Reports' }],
  '/backup': [{ label: 'Backup' }],
  '/administration': [{ label: 'Administration' }],
}

export default function Topbar({ title, onMenuClick }) {
  const location = useLocation()
  const navigate = useNavigate()
  const user = authService.getUser()
  const initials = user
    ? (user.first_name?.[0] || user.username?.[0] || '?').toUpperCase()
    : '?'

  const handleLogout = async () => {
    await authService.logout()
    navigate('/login', { replace: true })
  }

  const breadcrumbItems = useMemo(() => {
    const staticMatch = staticBreadcrumbMap[location.pathname]
    if (staticMatch) return staticMatch

    const occupantDetailMatch = location.pathname.match(/^\/occupants\/(\d+)$/)
    if (occupantDetailMatch) {
      return [
        { label: 'Occupants', path: '/occupants' },
        { label: `#${occupantDetailMatch[1]}` },
      ]
    }

    const occupantEditMatch = location.pathname.match(/^\/occupants\/(\d+)\/edit$/)
    if (occupantEditMatch) {
      return [
        { label: 'Occupants', path: '/occupants' },
        { label: `#${occupantEditMatch[1]}`, path: `/occupants/${occupantEditMatch[1]}` },
        { label: 'Edit' },
      ]
    }

    const segments = location.pathname.split('/').filter(Boolean)
    const lastSegment = segments[segments.length - 1]
    const derivedLabel = lastSegment
      ? lastSegment.replace(/[-_]+/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
      : 'Home'

    return [{ label: derivedLabel }]
  }, [location.pathname])

  return (
    <header className="h-16 bg-white border-b border-gray-200 flex items-center px-4 lg:px-8 gap-4 sticky top-0 z-30">
      <button
        onClick={onMenuClick}
        className="lg:hidden p-2 -ml-2 rounded-lg text-gray-500 hover:bg-gray-100 hover:text-gray-700 transition-colors"
        aria-label="Open sidebar"
      >
        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
        </svg>
      </button>

      <div className="flex-1 min-w-0">
        <h2 className="text-lg font-semibold text-gray-900 truncate">{title}</h2>
        <Breadcrumb items={breadcrumbItems} />
      </div>

      <div className="hidden sm:flex items-center gap-3 flex-shrink-0" data-tour="topbar-search">
        <kbd className="hidden md:inline-flex items-center gap-1 px-2 py-1 text-xs font-mono text-gray-400 bg-gray-100 rounded">
          <span className="text-gray-500">Ctrl</span>
          <span>+</span>
          <span>K</span>
        </kbd>
        <span className="text-sm text-gray-500">{user?.username || 'Property Manager'}</span>
        <div className="w-9 h-9 rounded-full bg-primary-100 flex items-center justify-center text-primary-700 font-semibold text-sm">
          {initials}
        </div>
        <button
          onClick={handleLogout}
          className="text-sm text-gray-500 hover:text-gray-700 font-medium"
        >
          Log out
        </button>
      </div>
    </header>
  )
}

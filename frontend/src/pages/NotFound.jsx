import { Link } from 'react-router-dom'
import Button from '../components/Button'
import Card from '../components/Card'

const quickLinks = [
  { label: 'Overview', href: '/', description: 'Dashboard and key metrics' },
  { label: 'Property Explorer', href: '/explorer', description: 'Browse units and occupancy' },
  { label: 'Occupants', href: '/occupants', description: 'Manage student records' },
  { label: 'Payments', href: '/payments', description: 'Track and record payments' },
  { label: 'Receipts', href: '/receipts', description: 'View and download receipts' },
  { label: 'Administration', href: '/administration', description: 'System configuration' },
]

export default function NotFound() {
  return (
    <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center p-8">
      <div className="text-center max-w-lg">
        <p className="text-8xl font-bold text-gray-200 mb-4">404</p>
        <h1 className="text-2xl font-bold text-gray-900 mb-2">Page not found</h1>
        <p className="text-gray-600 mb-8">
          The page you are looking for does not exist or has been moved. Try navigating from one of these pages:
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-8 text-left">
          {quickLinks.map((link) => (
            <Link
              key={link.href}
              to={link.href}
              className="block p-3 rounded-lg border border-gray-200 hover:border-primary-300 hover:bg-gray-50 transition-all"
            >
              <p className="text-sm font-medium text-gray-900">{link.label}</p>
              <p className="text-xs text-gray-500 mt-0.5">{link.description}</p>
            </Link>
          ))}
        </div>

        <Link to="/">
          <Button>Go to Overview</Button>
        </Link>
      </div>
    </div>
  )
}

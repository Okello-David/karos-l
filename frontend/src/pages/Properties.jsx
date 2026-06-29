import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import PageContainer from '../components/PageContainer'
import Card from '../components/Card'
import Button from '../components/Button'
import EmptyState from '../components/EmptyState'
import { Skeleton } from '../components/Skeleton'
import { explorerService } from '../services/explorer'

export default function Properties() {
  const [properties, setProperties] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    explorerService.getHierarchy('')
      .then((data) => {
        if (!cancelled) setProperties(data)
      })
      .catch((err) => {
        if (!cancelled) setError(err.message)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [])

  const totalProperties = properties?.length ?? 0
  const totalUnits = properties?.reduce((sum, p) => {
    return sum + (p.sections || []).reduce((s, sec) => s + (sec.units?.length || 0), 0)
  }, 0) ?? 0
  const totalCapacity = properties?.reduce((sum, p) => {
    return sum + (p.sections || []).reduce((s, sec) => s + (sec.units || []).reduce((u, unit) => u + (unit.capacity || 0), 0), 0)
  }, 0) ?? 0
  const totalOccupied = properties?.reduce((sum, p) => {
    return sum + (p.sections || []).reduce((s, sec) => s + (sec.units || []).reduce((u, unit) => u + (unit.current_occupant_count || 0), 0), 0)
  }, 0) ?? 0
  const occupancyRate = totalCapacity > 0 ? Math.round((totalOccupied / totalCapacity) * 100) : 0

  return (
    <PageContainer
      title="Properties"
      description="View all properties, sections, and units."
    >
      {/* Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 mb-6">
        <Card>
          <p className="text-sm text-gray-500">Total Properties</p>
          <p className="text-3xl font-bold text-gray-900 mt-2">
            {loading ? <Skeleton className="h-8 w-12 inline-block" /> : totalProperties}
          </p>
        </Card>
        <Card>
          <p className="text-sm text-gray-500">Total Units</p>
          <p className="text-3xl font-bold text-gray-900 mt-2">
            {loading ? <Skeleton className="h-8 w-12 inline-block" /> : totalUnits}
          </p>
        </Card>
        <Card>
          <p className="text-sm text-gray-500">Occupancy Rate</p>
          <p className="text-3xl font-bold text-gray-900 mt-2">
            {loading ? <Skeleton className="h-8 w-12 inline-block" /> : `${occupancyRate}%`}
          </p>
        </Card>
      </div>

      {loading && (
        <Card>
          <div className="space-y-4">
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-12 rounded-lg" />
            ))}
          </div>
        </Card>
      )}

      {error && (
        <Card>
          <div className="text-center py-8">
            <p className="text-red-600 mb-4">{error}</p>
          </div>
        </Card>
      )}

      {!loading && !error && (!properties || properties.length === 0) && (
        <EmptyState
          icon="building"
          title="No properties yet"
          description="Properties will appear here once you add them. Each property can contain sections and individual units."
          hint="Go to Administration → Properties tab to add your first property."
          action={
            <Button onClick={() => window.location.href = '/administration'}>
              Go to Administration
            </Button>
          }
        />
      )}

      {!loading && !error && properties && properties.length > 0 && (
        <Card title="Property Overview">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-3 px-4 font-medium text-gray-500">Name</th>
                  <th className="text-left py-3 px-4 font-medium text-gray-500">Code</th>
                  <th className="text-center py-3 px-4 font-medium text-gray-500">Sections</th>
                  <th className="text-center py-3 px-4 font-medium text-gray-500">Units</th>
                  <th className="text-center py-3 px-4 font-medium text-gray-500">Status</th>
                  <th className="text-right py-3 px-4 font-medium text-gray-500"></th>
                </tr>
              </thead>
              <tbody>
                {properties.map((prop) => {
                  const unitCount = (prop.sections || []).reduce((s, sec) => s + (sec.units?.length || 0), 0)
                  return (
                    <tr key={prop.id} className="border-b border-gray-100 hover:bg-gray-50 transition-colors">
                      <td className="py-3 px-4 font-medium text-gray-900">{prop.name}</td>
                      <td className="py-3 px-4 text-gray-600 font-mono">{prop.code || '—'}</td>
                      <td className="py-3 px-4 text-center text-gray-600">{(prop.sections || []).length}</td>
                      <td className="py-3 px-4 text-center text-gray-600">{unitCount}</td>
                      <td className="py-3 px-4 text-center">
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700">
                          Active
                        </span>
                      </td>
                      <td className="py-3 px-4 text-right">
                        <Link
                          to="/explorer"
                          className="text-sm text-primary-600 hover:text-primary-700"
                        >
                          View
                        </Link>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </PageContainer>
  )
}

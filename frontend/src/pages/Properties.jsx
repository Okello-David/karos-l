import PageContainer from '../components/PageContainer'
import Card from '../components/Card'
import Button from '../components/Button'
import EmptyState from '../components/EmptyState'
import { Skeleton } from '../components/Skeleton'
import { useExplorer } from '../hooks/useExplorer'

export default function Properties() {
  const { data: properties, loading, error, refetch } = useExplorer('')
  const totalProperties = properties?.length || 0
  const totalUnits = properties?.reduce(
    (sum, property) => sum + (property.sections || []).reduce(
      (sectionSum, section) => sectionSum + (section.units?.length || 0),
      0
    ),
    0
  ) || 0
  const occupiedSpaces = properties?.reduce(
    (sum, property) => sum + (property.sections || []).reduce(
      (sectionSum, section) => sectionSum + (section.units || []).reduce(
        (unitSum, unit) => unitSum + (unit.current_occupant_count || 0),
        0
      ),
      0
    ),
    0
  ) || 0
  const totalCapacity = properties?.reduce(
    (sum, property) => sum + (property.sections || []).reduce(
      (sectionSum, section) => sectionSum + (section.units || []).reduce(
        (unitSum, unit) => unitSum + (unit.capacity || 0),
        0
      ),
      0
    ),
    0
  ) || 0
  const occupancyRate = totalCapacity > 0 ? Math.round((occupiedSpaces / totalCapacity) * 100) : 0

  return (
    <PageContainer
      title="Properties"
      description="Manage your properties, sections, and units from one place."
    >
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
        <Card>
          <p className="text-sm text-gray-500">Total Properties</p>
          <div className="text-3xl font-bold text-gray-900 mt-2">{loading ? <Skeleton className="h-9 w-12" /> : totalProperties}</div>
        </Card>
        <Card>
          <p className="text-sm text-gray-500">Total Units</p>
          <div className="text-3xl font-bold text-gray-900 mt-2">{loading ? <Skeleton className="h-9 w-12" /> : totalUnits}</div>
        </Card>
        <Card>
          <p className="text-sm text-gray-500">Occupancy Rate</p>
          <div className="text-3xl font-bold text-gray-900 mt-2">{loading ? <Skeleton className="h-9 w-16" /> : `${occupancyRate}%`}</div>
        </Card>
      </div>

      {error && (
        <Card>
          <div className="text-center py-8">
            <p className="text-red-600 mb-4">{error}</p>
            <Button variant="secondary" onClick={refetch}>Try Again</Button>
          </div>
        </Card>
      )}

      {!loading && !error && totalProperties === 0 && (
        <EmptyState
          icon="building"
          title="No properties yet"
          description="Properties will appear here once you add them. Each property can contain sections and individual units."
          hint="Go to Administration &rarr; Properties tab to add your first property."
          action={
            <Button onClick={() => window.location.href = '/administration'}>
              Go to Administration
            </Button>
          }
        />
      )}

      <Card title="Property Overview">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="text-left py-3 px-4 font-medium text-gray-500">Name</th>
                <th className="text-left py-3 px-4 font-medium text-gray-500">Code</th>
                <th className="text-left py-3 px-4 font-medium text-gray-500">Units</th>
                <th className="text-left py-3 px-4 font-medium text-gray-500">Status</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr className="border-b border-gray-100">
                  <td className="py-3 px-4" colSpan={4}><Skeleton className="h-6" /></td>
                </tr>
              ) : properties?.length ? (
                properties.map((property) => {
                  const unitCount = (property.sections || []).reduce((sum, section) => sum + (section.units?.length || 0), 0)
                  return (
                    <tr key={property.id} className="border-b border-gray-100 last:border-0">
                      <td className="py-3 px-4 text-gray-900 font-medium">{property.name}</td>
                      <td className="py-3 px-4 text-gray-500 font-mono text-xs">{property.code || '—'}</td>
                      <td className="py-3 px-4 text-gray-500">{unitCount}</td>
                      <td className="py-3 px-4 text-gray-500">Active</td>
                    </tr>
                  )
                })
              ) : (
                <tr className="border-b border-gray-100">
                  <td className="py-3 px-4 text-gray-400" colSpan={4}>No data available yet</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </PageContainer>
  )
}

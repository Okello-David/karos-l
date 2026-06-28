import PageContainer from '../components/PageContainer'
import Card from '../components/Card'
import Button from '../components/Button'
import EmptyState from '../components/EmptyState'

export default function Properties() {
  return (
    <PageContainer
      title="Properties"
      description="Manage your properties, sections, and units from one place."
    >
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
        <Card>
          <p className="text-sm text-gray-500">Total Properties</p>
          <p className="text-3xl font-bold text-gray-900 mt-2">—</p>
        </Card>
        <Card>
          <p className="text-sm text-gray-500">Total Units</p>
          <p className="text-3xl font-bold text-gray-900 mt-2">—</p>
        </Card>
        <Card>
          <p className="text-sm text-gray-500">Occupancy Rate</p>
          <p className="text-3xl font-bold text-gray-900 mt-2">—</p>
        </Card>
      </div>

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
              <tr className="border-b border-gray-100">
                <td className="py-3 px-4 text-gray-400" colSpan={4}>
                  No data available yet
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </Card>
    </PageContainer>
  )
}

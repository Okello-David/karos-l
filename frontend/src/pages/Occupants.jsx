import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import PageContainer from '../components/PageContainer'
import Card from '../components/Card'
import Button from '../components/Button'
import { Skeleton } from '../components/Skeleton'
import EmptyState from '../components/EmptyState'
import { useOccupants } from '../hooks/useOccupants'

const statusTabs = [
  { label: 'All', value: '' },
  { label: 'Active', value: 'active' },
  { label: 'Archived', value: 'archived' },
]

export default function Occupants() {
  const navigate = useNavigate()
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('')
  const [page, setPage] = useState(1)
  const { data, loading, error, refetch } = useOccupants({ search, status, page })

  const handleSearch = (e) => {
    e.preventDefault()
    setPage(1)
  }

  const handleStatusChange = (value) => {
    setStatus(value)
    setPage(1)
  }

  const handlePrevPage = () => {
    setPage((p) => Math.max(1, p - 1))
  }

  const handleNextPage = () => {
    setPage((p) => p + 1)
  }

  return (
    <PageContainer
      title="Occupants"
      description="Manage students and their records."
    >
      <Card>
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <form onSubmit={handleSearch} className="flex-1 max-w-md">
              <label htmlFor="search" className="sr-only">Search occupants</label>
              <input
                id="search"
                type="text"
                placeholder="Search by name, phone, ID..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              />
            </form>
            <Button onClick={() => navigate('/occupants/new')}>
              Add Occupant
            </Button>
          </div>

          <div className="flex gap-1 bg-gray-100 rounded-lg p-1 w-fit" role="tablist">
            {statusTabs.map((tab) => (
              <button
                key={tab.value}
                role="tab"
                aria-selected={status === tab.value}
                onClick={() => handleStatusChange(tab.value)}
                className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                  status === tab.value
                    ? 'bg-white text-gray-900 shadow-sm'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>
      </Card>

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
            <Button variant="secondary" onClick={refetch}>Try Again</Button>
          </div>
        </Card>
      )}

        {!loading && !error && data && data.count === 0 && (
        <EmptyState
          icon={search ? 'search' : 'people'}
          title={search ? 'No occupants match your search' : 'No occupants yet'}
          description={
            search
              ? 'Try a different name or ID.'
              : 'Add your first occupant to get started.'
          }
          hint={
            search ? undefined : 'You can register occupants manually or import them via the Backup & Export page.'
          }
          action={
            search ? (
              <Button variant="secondary" onClick={() => { setSearch(''); setPage(1) }}>
                Clear Search
              </Button>
            ) : (
              <Button onClick={() => navigate('/occupants/new')}>
                Add Occupant
              </Button>
            )
          }
        />
      )}

      {!loading && !error && data && data.count > 0 && (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-3 px-4 font-medium text-gray-500">Name</th>
                  <th className="text-left py-3 px-4 font-medium text-gray-500 hidden sm:table-cell">Email</th>
                  <th className="text-left py-3 px-4 font-medium text-gray-500 hidden md:table-cell">Phone</th>
                  <th className="text-left py-3 px-4 font-medium text-gray-500 hidden lg:table-cell">Student ID</th>
                  <th className="text-left py-3 px-4 font-medium text-gray-500">Status</th>
                  <th className="text-right py-3 px-4 font-medium text-gray-500">Actions</th>
                </tr>
              </thead>
              <tbody>
                {data.results.map((occupant) => (
                  <tr key={occupant.id} className="border-b border-gray-100 hover:bg-gray-50 transition-colors">
                    <td className="py-3 px-4">
                      <Link
                        to={`/occupants/${occupant.id}`}
                        className="text-primary-600 hover:text-primary-700 font-medium"
                      >
                        {occupant.full_name}
                      </Link>
                    </td>
                    <td className="py-3 px-4 text-gray-600 hidden sm:table-cell">{occupant.email || '—'}</td>
                    <td className="py-3 px-4 text-gray-600 hidden md:table-cell">{occupant.phone || '—'}</td>
                    <td className="py-3 px-4 text-gray-600 hidden lg:table-cell">{occupant.student_id_number || '—'}</td>
                    <td className="py-3 px-4">
                      <span
                        className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                          occupant.is_active
                            ? 'bg-green-100 text-green-700'
                            : 'bg-gray-100 text-gray-500'
                        }`}
                      >
                        {occupant.is_active ? 'Active' : 'Archived'}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right">
                      <Link
                        to={`/occupants/${occupant.id}`}
                        className="text-sm text-primary-600 hover:text-primary-700 mr-3"
                      >
                        View
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {data.total_pages > 1 && (
            <div className="flex items-center justify-between pt-4 border-t border-gray-100 mt-4">
              <p className="text-sm text-gray-500">
                Page {data.page} of {data.total_pages} ({data.count} total)
              </p>
              <div className="flex gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={page <= 1}
                  onClick={handlePrevPage}
                >
                  Previous
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={page >= data.total_pages}
                  onClick={handleNextPage}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </Card>
      )}
    </PageContainer>
  )
}

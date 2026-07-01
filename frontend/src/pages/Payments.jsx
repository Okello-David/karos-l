import { useState } from 'react'
import { useNavigate, Link, useSearchParams } from 'react-router-dom'
import PageContainer from '../components/PageContainer'
import Card from '../components/Card'
import Button from '../components/Button'
import { Skeleton } from '../components/Skeleton'
import EmptyState from '../components/EmptyState'
import PaymentDetailDialog from '../components/PaymentDetailDialog'
import { usePayments, useOverdueStudents } from '../hooks/usePayments'
import { useOccupancySummary } from '../hooks/useOccupancy'

const methodLabels = {
  cash: 'Cash',
  transfer: 'Bank Transfer',
  card: 'Card',
}

export default function Payments() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const [search, setSearch] = useState('')
  const [methodFilter, setMethodFilter] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [page, setPage] = useState(1)

  const params = {}
  if (search) params.search = search
  if (methodFilter) params.payment_method = methodFilter
  if (dateFrom) params.date_from = dateFrom
  if (dateTo) params.date_to = dateTo
  const studentFilter = searchParams.get('student')
  if (studentFilter) params.student_id = studentFilter
  params.page = page
  params.page_size = 20

  const { data: payments, loading, error, refetch } = usePayments(params)
  const { data: overdue } = useOverdueStudents()
  const { data: summary } = useOccupancySummary()

  const [detailOpen, setDetailOpen] = useState(false)
  const [detailPayment, setDetailPayment] = useState(null)

  const handleViewDetail = (payment) => {
    setDetailPayment(payment)
    setDetailOpen(true)
  }

  const handleSearch = (e) => {
    e.preventDefault()
    setPage(1)
  }

  const clearStudentFilter = () => {
    const next = new URLSearchParams(searchParams)
    next.delete('student')
    setSearchParams(next, { replace: true })
    setPage(1)
  }

  const totalCollected = payments?.results?.reduce(
    (sum, p) => sum + Number(p.amount), 0
  ) || 0

  const overdueCount = overdue?.count || 0

  return (
    <PageContainer
      title="Payments"
      description="Track payments, record new transactions, and view outstanding balances."
    >
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
        <Card>
          <p className="text-sm text-gray-500">Total Collected</p>
          <p className="text-3xl font-bold text-gray-900 mt-2">
            UGX {totalCollected.toLocaleString('en-UG')}
          </p>
          <p className="text-xs text-gray-400 mt-1">
            From {payments?.count || 0} payments
          </p>
        </Card>
        <Card>
          <p className="text-sm text-gray-500">Occupied Beds</p>
          <p className="text-3xl font-bold text-gray-900 mt-2">
            {summary?.total_occupied ?? '...'}
          </p>
          <p className="text-xs text-gray-400 mt-1">
            Out of {summary?.total_capacity ?? '...'} total
          </p>
        </Card>
        <Card>
          <p className="text-sm text-gray-500">Outstanding</p>
          <p className="text-3xl font-bold text-red-600 mt-2">{overdueCount}</p>
          <p className="text-xs text-gray-400 mt-1">
            Occupants with overdue balances
          </p>
        </Card>
      </div>

      <Card>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Link
              to="/receipts"
              className="text-sm text-primary-600 hover:text-primary-700 font-medium"
            >
              View Receipts &rarr;
            </Link>
            <Button onClick={() => navigate('/occupants')}>Choose Occupant</Button>
          </div>
        </div>

        {studentFilter && (
          <div className="flex items-center justify-between gap-3 mb-4 rounded-lg bg-primary-50 px-4 py-2 text-sm text-primary-800">
            <span>Showing payments for selected occupant.</span>
            <button type="button" onClick={clearStudentFilter} className="font-medium text-primary-700 hover:text-primary-900">
              Clear filter
            </button>
          </div>
        )}

        <form onSubmit={handleSearch} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 mb-4">
          <input
            type="text"
            placeholder="Search occupant or reference..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
          <select
            value={methodFilter}
            onChange={(e) => { setMethodFilter(e.target.value); setPage(1) }}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            <option value="">All Methods</option>
            <option value="cash">Cash</option>
            <option value="transfer">Bank Transfer</option>
            <option value="card">Card</option>
          </select>
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => { setDateFrom(e.target.value); setPage(1) }}
            placeholder="From date"
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
          <input
            type="date"
            value={dateTo}
            onChange={(e) => { setDateTo(e.target.value); setPage(1) }}
            placeholder="To date"
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
          <Button variant="secondary" type="submit">Search</Button>
        </form>

        {loading ? (
          <div className="space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-12" />
            ))}
          </div>
        ) : error ? (
          <div className="text-center py-8">
            <p className="text-red-600 mb-4">{error}</p>
            <Button variant="secondary" onClick={refetch}>Try Again</Button>
          </div>
        ) : !payments?.results?.length ? (
          <EmptyState
            icon="currency"
            title={search ? 'No payments match your search' : 'No payments recorded'}
            description={
              search || studentFilter
                ? 'Try a different search term or date range.'
                : 'Payments will appear here once you start recording them.'
            }
          />
        ) : (
          <>
            <div className="overflow-x-auto -mx-6">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200">
                    <th className="text-left py-3 px-6 font-medium text-gray-500">Occupant</th>
                    <th className="text-left py-3 px-6 font-medium text-gray-500">Amount</th>
                    <th className="text-left py-3 px-6 font-medium text-gray-500">Date</th>
                    <th className="text-left py-3 px-6 font-medium text-gray-500">Method</th>
                    <th className="text-left py-3 px-6 font-medium text-gray-500">Reference</th>
                    <th className="text-left py-3 px-6 font-medium text-gray-500">Notes</th>
                    <th className="text-left py-3 px-6 font-medium text-gray-500" />
                  </tr>
                </thead>
                <tbody>
                  {payments.results.map((p) => (
                    <tr
                      key={p.id}
                      className="border-b border-gray-100 last:border-0 hover:bg-gray-50 transition-colors cursor-pointer"
                      onClick={() => handleViewDetail(p)}
                    >
                      <td className="py-3 px-6 text-gray-900 font-medium">{p.student_name}</td>
                      <td className="py-3 px-6 text-gray-900">
                        UGX {Number(p.amount).toLocaleString('en-UG')}
                      </td>
                      <td className="py-3 px-6 text-gray-500">
                        {new Date(p.payment_date).toLocaleDateString()}
                      </td>
                      <td className="py-3 px-6 text-gray-500">{methodLabels[p.payment_method] || p.payment_method}</td>
                      <td className="py-3 px-6 text-gray-500">{p.reference || '—'}</td>
                      <td className="py-3 px-6 text-gray-500 max-w-[150px] truncate">{p.notes || '—'}</td>
                      <td className="py-3 px-6">
                        <button
                          onClick={(e) => { e.stopPropagation(); handleViewDetail(p) }}
                          className="text-primary-600 hover:text-primary-700 text-sm font-medium"
                        >
                          View
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {payments.total_pages > 1 && (
              <div className="flex items-center justify-between pt-4">
                <p className="text-sm text-gray-500">
                  Page {payments.page} of {payments.total_pages}
                </p>
                <div className="flex gap-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={page <= 1}
                    onClick={() => setPage(page - 1)}
                  >
                    Previous
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={page >= payments.total_pages}
                    onClick={() => setPage(page + 1)}
                  >
                    Next
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card title="Overdue Balances">
          {!overdue ? (
            <Skeleton className="h-20" />
          ) : overdue.results?.length > 0 ? (
            <div className="space-y-3">
              {overdue.results.slice(0, 5).map((item) => (
                <div
                  key={item.student_id}
                  className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0"
                >
                  <div>
                    <p className="text-sm font-medium text-gray-900">{item.student_name}</p>
                    <p className="text-xs text-gray-500">
                      {item.unit_name ? `${item.property_name} / ${item.unit_name}` : 'No unit'}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-semibold text-red-600">
                      UGX {Number(item.balance).toLocaleString('en-UG')}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState
              icon="currency"
              title="All caught up"
              description="No outstanding balances. All occupants are up to date."
            />
          )}
        </Card>

        <Card title="Payment Methods">
          <div className="space-y-3">
            {['cash', 'transfer', 'card'].map((method) => {
              const count = payments?.results?.filter((p) => p.payment_method === method).length || 0
              const total = payments?.results?.filter((p) => p.payment_method === method)
                .reduce((s, p) => s + Number(p.amount), 0) || 0
              return (
                <div key={method} className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0">
                  <span className="text-sm text-gray-700">{methodLabels[method]}</span>
                  <span className="text-sm text-gray-500">
                    {count} payments &middot; UGX {total.toLocaleString('en-UG')}
                  </span>
                </div>
              )
            })}
          </div>
        </Card>
      </div>

      <PaymentDetailDialog
        open={detailOpen}
        payment={detailPayment}
        onClose={() => setDetailOpen(false)}
      />
    </PageContainer>
  )
}

import { useState } from 'react'
import PageContainer from '../components/PageContainer'
import Card from '../components/Card'
import Button from '../components/Button'
import { Skeleton } from '../components/Skeleton'
import EmptyState from '../components/EmptyState'
import { useReceipts } from '../hooks/usePayments'
import { paymentsService } from '../services/payments'
import { formatUGX } from '../utils/format'

export default function Receipts() {
  const [search, setSearch] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [page, setPage] = useState(1)
  const [pdfError, setPdfError] = useState(null)

  const params = {}
  if (search) params.search = search
  if (dateFrom) params.date_from = dateFrom
  if (dateTo) params.date_to = dateTo
  params.page = page
  params.page_size = 20

  const { data, loading, error, refetch } = useReceipts(params)

  const handleSearch = (e) => {
    e.preventDefault()
    setPage(1)
  }

  const handlePdf = async (receiptId) => {
    setPdfError(null)
    try {
      const blob = await paymentsService.receiptPdf(receiptId)
      const url = URL.createObjectURL(blob)
      window.open(url, '_blank', 'noopener,noreferrer')
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (err) {
      setPdfError(err.message)
    }
  }

  return (
    <PageContainer
      title="Receipts"
      description="Browse payment receipts and print or download as PDF."
    >
      <Card>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900">Payment Receipts</h3>
        </div>

        <form onSubmit={handleSearch} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
          <input
            type="text"
            placeholder="Search receipt #, occupant, or reference..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
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

        {pdfError && <p className="text-sm text-red-600 mb-4">{pdfError}</p>}

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
        ) : !data?.results?.length ? (
          <EmptyState
            icon="receipt"
            title={search ? 'No receipts match your search' : 'No receipts yet'}
            description={
              search
                ? 'Try a different receipt number or date range.'
                : 'Receipts are automatically generated when payments are recorded.'
            }
          />
        ) : (
          <>
            <div className="overflow-x-auto -mx-6">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200">
                    <th className="text-left py-3 px-6 font-medium text-gray-500">Receipt #</th>
                    <th className="text-left py-3 px-6 font-medium text-gray-500">Occupant</th>
                    <th className="text-left py-3 px-6 font-medium text-gray-500">Amount</th>
                    <th className="text-left py-3 px-6 font-medium text-gray-500 hidden sm:table-cell">Date</th>
                    <th className="text-left py-3 px-6 font-medium text-gray-500 hidden md:table-cell">Method</th>
                    <th className="text-left py-3 px-6 font-medium text-gray-500 hidden lg:table-cell">Unit</th>
                    <th className="text-left py-3 px-6 font-medium text-gray-500" />
                  </tr>
                </thead>
                <tbody>
                  {data.results.map((r) => (
                    <tr
                      key={r.id}
                      className="border-b border-gray-100 last:border-0 hover:bg-gray-50 transition-colors"
                    >
                      <td className="py-3 px-6 font-mono text-xs text-primary-700 font-medium">
                        {r.receipt_number}
                      </td>
                      <td className="py-3 px-6 text-gray-900 font-medium">{r.student_name}</td>
                      <td className="py-3 px-6 text-gray-900">
                        {formatUGX(r.amount)}
                      </td>
                      <td className="py-3 px-6 text-gray-500 hidden sm:table-cell">
                        {new Date(r.payment_date).toLocaleDateString()}
                      </td>
                      <td className="py-3 px-6 text-gray-500 capitalize hidden md:table-cell">{r.payment_method}</td>
                      <td className="py-3 px-6 text-gray-500 hidden lg:table-cell">{r.unit_name || '—'}</td>
                      <td className="py-3 px-6">
                        <button
                          type="button"
                          onClick={() => handlePdf(r.id)}
                          className="text-primary-600 hover:text-primary-700 text-sm font-medium"
                        >
                          PDF
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {data.total_pages > 1 && (
              <div className="flex items-center justify-between pt-4">
                <p className="text-sm text-gray-500">
                  Page {data.page} of {data.total_pages}
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
                    disabled={page >= data.total_pages}
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
    </PageContainer>
  )
}

import { useCallback, useEffect, useState } from 'react'
import PageContainer from '../components/PageContainer'
import Button from '../components/Button'
import EmptyState from '../components/EmptyState'
import { Skeleton } from '../components/Skeleton'
import { reportsService } from '../services/reports'
import { formatUGX } from '../utils/format'

const REPORTS = {
  occupancy: {
    title: 'Occupancy Reports',
    description: 'Occupancy rates, capacity and utilisation across all properties.',
    accent: 'text-primary-500',
    icon: (
      <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75ZM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625ZM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125Z" />
      </svg>
    ),
    columns: [
      { header: 'Property', key: 'property' },
      { header: 'Code', key: 'code' },
      { header: 'Units', key: 'units', align: 'right', hide: 'hidden sm:table-cell' },
      { header: 'Capacity', key: 'capacity', align: 'right' },
      { header: 'Occupied', key: 'occupied', align: 'right' },
      { header: 'Available', key: 'available', align: 'right', hide: 'hidden md:table-cell' },
      { header: 'Occupancy Rate', key: 'occupancy_rate', align: 'right', format: (v) => `${v}%` },
    ],
    tiles: (s) => [
      { label: 'Properties', value: s.total_properties },
      { label: 'Total capacity', value: s.total_capacity },
      { label: 'Occupied', value: s.total_occupied },
      { label: 'Occupancy rate', value: `${s.occupancy_rate}%` },
    ],
  },
  financial: {
    title: 'Financial Reports',
    description: 'Payment collections, outstanding balances and revenue summaries.',
    accent: 'text-emerald-500',
    icon: (
      <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v12m-3-2.818.879.659c1.171.879 3.07.879 4.242 0 1.172-.879 1.172-2.303 0-3.182C13.536 12.219 12.768 12 12 12c-.725 0-1.45-.22-2.003-.659-1.106-.879-1.106-2.303 0-3.182s2.9-.879 4.006 0l.415.33M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
    columns: [
      { header: 'Property', key: 'property' },
      { header: 'Code', key: 'code', hide: 'hidden sm:table-cell' },
      { header: 'Payments', key: 'payments', align: 'right', hide: 'hidden md:table-cell' },
      { header: 'Collected', key: 'collected', align: 'right', format: formatUGX },
      { header: 'Outstanding', key: 'outstanding', align: 'right', format: formatUGX },
    ],
    tiles: (s) => [
      { label: 'Collected', value: formatUGX(s.total_collected) },
      { label: 'Outstanding', value: formatUGX(s.total_outstanding) },
      { label: 'Payments', value: s.payment_count },
      { label: 'In arrears', value: s.occupants_in_arrears },
    ],
  },
  occupants: {
    title: 'Student Reports',
    description: 'Occupant lists, contact details, unit assignments and balances.',
    accent: 'text-blue-500',
    icon: (
      <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" d="M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z" />
      </svg>
    ),
    columns: [
      { header: 'Name', key: 'name' },
      { header: 'Student ID', key: 'student_id', hide: 'hidden sm:table-cell' },
      { header: 'Phone', key: 'phone', hide: 'hidden lg:table-cell' },
      { header: 'Property', key: 'property', hide: 'hidden md:table-cell' },
      { header: 'Unit', key: 'unit' },
      { header: 'Status', key: 'status' },
      { header: 'Balance', key: 'balance', align: 'right', format: formatUGX },
    ],
    tiles: (s) => [
      { label: 'Occupants', value: s.total_occupants },
      { label: 'Assigned', value: s.assigned },
      { label: 'Unassigned', value: s.unassigned },
    ],
  },
}

function SummaryTiles({ tiles }) {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
      {tiles.map((tile) => (
        <div key={tile.label} className="bg-gray-50 rounded-lg p-4">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">{tile.label}</p>
          <p className="mt-1 text-xl font-semibold text-gray-900">{tile.value}</p>
        </div>
      ))}
    </div>
  )
}

export default function Reports() {
  const [selected, setSelected] = useState('occupancy')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [exporting, setExporting] = useState(false)

  // Applied values drive the request; the inputs are separate so typing a date
  // does not fire a request on every keystroke.
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [range, setRange] = useState({ start_date: '', end_date: '' })

  const load = useCallback(() => {
    setLoading(true)
    setError(null)
    const request =
      selected === 'financial'
        ? reportsService.financial(range)
        : reportsService[selected]()

    return request
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [selected, range])

  useEffect(() => { load() }, [load])

  const config = REPORTS[selected]

  function selectReport(key) {
    if (key === selected) return
    setSelected(key)
    setData(null)
    setStartDate('')
    setEndDate('')
    setRange({ start_date: '', end_date: '' })
  }

  function applyRange(event) {
    event.preventDefault()
    setRange({ start_date: startDate, end_date: endDate })
  }

  function handleExport(fileFormat) {
    setExporting(true)
    setError(null)
    reportsService
      .export(selected, fileFormat, selected === 'financial' ? range : {})
      .catch((err) => setError(err.message))
      .finally(() => setExporting(false))
  }

  const rows = data?.rows ?? []

  return (
    <PageContainer
      title="Reports & Analytics"
      description="Generate and view reports on occupancy, finances, and occupants."
    >
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {Object.entries(REPORTS).map(([key, report]) => {
          const isSelected = key === selected
          return (
            <button
              key={key}
              type="button"
              onClick={() => selectReport(key)}
              aria-pressed={isSelected}
              className={`text-left bg-white rounded-xl border p-6 transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 ${
                isSelected
                  ? 'border-primary-500 shadow-sm'
                  : 'border-gray-200 hover:border-primary-300 hover:shadow-sm'
              }`}
            >
              <div className={`mb-4 ${report.accent}`}>{report.icon}</div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">{report.title}</h3>
              <p className="text-sm text-gray-600">{report.description}</p>
            </button>
          )
        })}
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
          <h3 className="text-lg font-semibold text-gray-900">{config.title}</h3>
          <div className="flex gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => handleExport('csv')}
              disabled={exporting || loading || !rows.length}
            >
              Export CSV
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => handleExport('xlsx')}
              disabled={exporting || loading || !rows.length}
            >
              Export Excel
            </Button>
          </div>
        </div>

        {selected === 'financial' && (
          <form onSubmit={applyRange} className="flex flex-wrap gap-3 mb-6">
            <input
              type="date"
              aria-label="From date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
            <input
              type="date"
              aria-label="To date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
            <Button variant="secondary" type="submit">Apply</Button>
            {(range.start_date || range.end_date) && (
              <Button
                variant="ghost"
                type="button"
                onClick={() => {
                  setStartDate('')
                  setEndDate('')
                  setRange({ start_date: '', end_date: '' })
                }}
              >
                Clear
              </Button>
            )}
          </form>
        )}

        {loading ? (
          <div className="space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-12" />
            ))}
          </div>
        ) : error ? (
          <div className="text-center py-8">
            <p className="text-red-600 mb-4">{error}</p>
            <Button variant="secondary" onClick={load}>Try Again</Button>
          </div>
        ) : (
          <>
            {data?.summary && <SummaryTiles tiles={config.tiles(data.summary)} />}

            {!rows.length ? (
              <EmptyState
                icon={selected === 'occupants' ? 'people' : 'default'}
                title="Nothing to report yet"
                description={
                  selected === 'financial' && (range.start_date || range.end_date)
                    ? 'No payments fall within the selected dates. Try a wider range.'
                    : 'This report will fill in as properties, occupants and payments are added.'
                }
              />
            ) : (
              <div className="overflow-x-auto -mx-6">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-200">
                      {config.columns.map((column) => (
                        <th
                          key={column.key}
                          className={`py-3 px-6 font-medium text-gray-500 ${
                            column.align === 'right' ? 'text-right' : 'text-left'
                          } ${column.hide || ''}`}
                        >
                          {column.header}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row, index) => (
                      <tr key={`${row[config.columns[0].key]}-${index}`} className="border-b border-gray-100">
                        {config.columns.map((column) => (
                          <td
                            key={column.key}
                            className={`py-3 px-6 text-gray-900 ${
                              column.align === 'right' ? 'text-right' : 'text-left'
                            } ${column.hide || ''}`}
                          >
                            {column.format ? column.format(row[column.key]) : (row[column.key] || '—')}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {selected === 'financial' && data?.by_method?.length > 0 && (
              <div className="mt-6 pt-6 border-t border-gray-100">
                <h4 className="text-sm font-medium text-gray-500 mb-3">By payment method</h4>
                <div className="flex flex-wrap gap-3">
                  {data.by_method.map((method) => (
                    <div key={method.method} className="bg-gray-50 rounded-lg px-4 py-3">
                      <p className="text-xs text-gray-500 capitalize">{method.method}</p>
                      <p className="text-sm font-semibold text-gray-900">{formatUGX(method.amount)}</p>
                      <p className="text-xs text-gray-400">{method.count} payment{method.count === 1 ? '' : 's'}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </PageContainer>
  )
}

import { useNavigate } from 'react-router-dom'
import PageContainer from '../components/PageContainer'
import Card from '../components/Card'
import Button from '../components/Button'
import EmptyState from '../components/EmptyState'
import { Skeleton, CardSkeleton } from '../components/Skeleton'
import StatisticCard from '../components/dashboard/StatisticCard'
import PropertySummaryCard from '../components/dashboard/PropertySummaryCard'
import PaymentTable from '../components/dashboard/PaymentTable'
import { useOccupancySummary } from '../hooks/useOccupancy'
import { usePayments, useOverdueStudents } from '../hooks/usePayments'
import { useAuditLogs } from '../hooks/useAudit'
import { formatUGX } from '../utils/format'

export default function Dashboard() {
  const navigate = useNavigate()
  const { data: summary, loading: occLoading } = useOccupancySummary()
  const { data: recentPayments, loading: pmtLoading } = usePayments({ page_size: 5 })
  const { data: overdue } = useOverdueStudents()
  const { data: activity, loading: actLoading, error: actError } = useAuditLogs({ page_size: 5 })

  const livePayments = recentPayments?.results?.map((p) => ({
    id: p.id,
    occupant: p.student_name,
    amount: Number(p.amount),
    date: new Date(p.payment_date).toLocaleDateString('en-UG', { day: 'numeric', month: 'short', year: 'numeric' }),
    property: '—',
  })) || []

  const activityItems = activity?.results || []

  const overdueCount = overdue?.count || 0
  const overdueTotal = overdueCount > 0
    ? overdue.results.reduce((s, r) => s + Number(r.balance), 0)
    : 0

  return (
    <PageContainer
      title="Overview"
      description={overdueCount > 0
        ? `${overdueCount} occupant${overdueCount !== 1 ? 's' : ''} ha${overdueCount !== 1 ? 've' : 's'} outstanding payments needing attention.`
        : 'All occupants are up to date on payments.'}
    >
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
        <StatisticCard
          title="Occupied Beds"
          value={occLoading ? <Skeleton className="h-8 w-16 inline-block" /> : summary?.total_occupied ?? 0}
          subtitle={occLoading ? '' : `/ ${summary?.total_capacity ?? 0}`}
          secondary={{
            value: occLoading ? <Skeleton className="h-4 w-12 inline-block" /> : summary?.total_available ?? 0,
            label: 'Available',
          }}
          action={
            <Button variant="secondary" size="sm" onClick={() => navigate('/explorer')}>
              View Property Map
            </Button>
          }
        />

        <StatisticCard
          title="Outstanding Payments"
          value={overdue?.count ?? <Skeleton className="h-8 w-12 inline-block" />}
          subtitle="occupants owing"
          secondary={{
            value: overdueCount > 0 ? formatUGX(overdueTotal) : 'UGX 0',
            label: 'Total outstanding',
          }}
          action={
            <Button variant="secondary" size="sm" onClick={() => navigate('/payments')}>
              View Payments
            </Button>
          }
        />

        <StatisticCard
          title="Occupants"
          value={occLoading ? <Skeleton className="h-8 w-12 inline-block" /> : summary?.total_students ?? 0}
          subtitle="registered"
          secondary={{
            value: summary?.active_students ?? 0,
            label: 'Active',
          }}
          action={
            <Button variant="secondary" size="sm" onClick={() => navigate('/occupants')}>
              View Occupants
            </Button>
          }
        />

        <Card className="flex flex-col">
          <p className="text-sm font-medium text-gray-500 mb-3">Quick Actions</p>
          <div className="space-y-2 flex-1 flex flex-col justify-center" data-tour="actions">
            <button
              onClick={() => navigate('/occupants/new')}
              className="w-full flex items-center gap-3 px-4 py-3 rounded-lg border border-gray-200 text-sm font-medium text-gray-700 hover:bg-primary-50 hover:border-primary-300 hover:text-primary-700 transition-all"
            >
              <svg className="w-5 h-5 text-gray-400" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 7.5v3m0 0v3m0-3h3m-3 0h-3m-2.25-4.125a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zM4 19.235v-.11a6.375 6.375 0 0112.75 0v.109A12.318 12.318 0 0110.374 21c-2.331 0-4.512-.645-6.374-1.766z" />
              </svg>
              Register Occupant
            </button>
            <button
              onClick={() => navigate('/occupants')}
              className="w-full flex items-center gap-3 px-4 py-3 rounded-lg border border-gray-200 text-sm font-medium text-gray-700 hover:bg-primary-50 hover:border-primary-300 hover:text-primary-700 transition-all"
            >
              <svg className="w-5 h-5 text-gray-400" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v12m-3-2.818.879.659c1.171.879 3.07.879 4.242 0 1.172-.879 1.172-2.303 0-3.182C13.536 12.219 12.768 12 12 12c-.725 0-1.45-.22-2.003-.659-1.106-.879-1.106-2.303 0-3.182s2.9-.879 4.006 0l.415.33M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              Record Payment
            </button>
            <button
              onClick={() => navigate('/explorer')}
              className="w-full flex items-center gap-3 px-4 py-3 rounded-lg border border-gray-200 text-sm font-medium text-gray-700 hover:bg-primary-50 hover:border-primary-300 hover:text-primary-700 transition-all"
            >
              <svg className="w-5 h-5 text-gray-400" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 6.75V15m6-6v8.25m.503 3.498l4.875-2.437c.381-.19.622-.58.622-1.006V4.82c0-.836-.88-1.38-1.628-1.006l-3.869 1.934c-.317.159-.69.159-1.006 0L9.503 3.252a1.125 1.125 0 00-1.006 0L3.622 5.689C3.24 5.88 3 6.27 3 6.695V19.18c0 .836.88 1.38 1.628 1.006l3.869-1.934c.317-.159.69-.159 1.006 0l4.994 2.497c.317.158.69.158 1.006 0z" />
              </svg>
              Browse Explorer
            </button>
          </div>
        </Card>
      </div>

      <div>
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Properties Overview</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
          {occLoading ? (
            <CardSkeleton count={3} height="h-24" />
          ) : summary?.properties?.length > 0 ? (
            summary.properties.map((p) => (
              <PropertySummaryCard
                key={p.id}
                name={p.name}
                occupied={p.occupied}
                total={p.total_capacity}
                occupancyRate={p.occupancy_rate}
              />
            ))
          ) : (
            <div className="col-span-full">
              <div className="py-4"><EmptyState icon="building" title="No properties yet" description="Properties will appear here once they are configured." /></div>
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <div className="xl:col-span-2">
          <PaymentTable
            title="Recent Payments"
            payments={livePayments}
            loading={pmtLoading}
          />
        </div>

        <Card title="Recent Activity">
          {actLoading ? (
            <div className="space-y-4">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="flex gap-3">
                  <Skeleton className="w-2.5 h-2.5 rounded-full mt-1.5 shrink-0" />
                  <div className="flex-1">
                    <Skeleton className="h-4 w-3/4 mb-1" />
                    <Skeleton className="h-3 w-1/2" />
                  </div>
                </div>
              ))}
            </div>
          ) : actError ? (
            <p className="text-sm text-gray-500 text-center py-8">Recent activity is unavailable.</p>
          ) : activityItems.length > 0 ? (
            <div className="space-y-0">
              {activityItems.map((log, i) => {
                const actionColors = {
                  create: 'bg-green-400',
                  update: 'bg-blue-400',
                  assign: 'bg-purple-400',
                  checkout: 'bg-orange-400',
                  record_payment: 'bg-teal-400',
                  archive: 'bg-yellow-400',
                }
                const color = actionColors[log.action] || 'bg-gray-300'
                return (
                  <div key={log.id} className="flex gap-4 py-3 border-b border-gray-100 last:border-0">
                    <div className="flex flex-col items-center">
                      <div className={`w-2.5 h-2.5 rounded-full mt-1.5 ${color}`} />
                      {i < activityItems.length - 1 && <div className="w-px flex-1 bg-gray-100 mt-1" />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-gray-900 truncate">{log.description}</p>
                      <p className="text-xs text-gray-400 mt-0.5">
                        {new Date(log.timestamp).toLocaleString()}
                      </p>
                    </div>
                  </div>
                )
              })}
            </div>
          ) : (
            <EmptyState icon="default" title="No recent activity" description="Audit events will appear here." />
          )}
        </Card>
      </div>
    </PageContainer>
  )
}


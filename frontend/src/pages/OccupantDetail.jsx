import { useState, useEffect } from 'react'
import { useParams, Link, useSearchParams } from 'react-router-dom'
import PageContainer from '../components/PageContainer'
import Card from '../components/Card'
import Button from '../components/Button'
import EmptyState from '../components/EmptyState'
import { Skeleton, TableSkeleton, CardSkeleton } from '../components/Skeleton'
import ConfirmDialog from '../components/ConfirmDialog'
import AssignOccupancyDialog from '../components/AssignOccupancyDialog'
import RecordPaymentDialog from '../components/RecordPaymentDialog'
import { useOccupant } from '../hooks/useOccupants'
import { useActiveOccupancy, useOccupancyHistory } from '../hooks/useOccupancy'
import { useStudentBalance, useStudentPaymentHistory } from '../hooks/usePayments'
import { occupantsService } from '../services/occupants'
import { occupancyService } from '../services/occupancy'
import { useToast } from '../components/Toast'
import { formatUGX } from '../utils/format'

const methodLabels = {
  cash: 'Cash',
  transfer: 'Bank Transfer',
  card: 'Card',
}

export default function OccupantDetail() {
  const { id } = useParams()
  const [searchParams, setSearchParams] = useSearchParams()
  const { addToast } = useToast()
  const { data: occupant, loading, error, refetch } = useOccupant(id)
  const { data: activeOccupancy, loading: occLoading, refetch: refetchOcc } = useActiveOccupancy(id)
  const { data: history, loading: histLoading, refetch: refetchHist } = useOccupancyHistory(id)
  const { data: balance, loading: balLoading, refetch: refetchBal } = useStudentBalance(id)
  const { data: payments, loading: pmtLoading, refetch: refetchPmt } = useStudentPaymentHistory(id)

  const [archiveOpen, setArchiveOpen] = useState(false)
  const [archiving, setArchiving] = useState(false)
  const [assignOpen, setAssignOpen] = useState(false)
  const [checkoutOpen, setCheckoutOpen] = useState(false)
  const [checkingOut, setCheckingOut] = useState(false)
  const [recordPmtOpen, setRecordPmtOpen] = useState(false)
  const [actionError, setActionError] = useState(null)

  const handleArchive = async () => {
    setArchiving(true)
    setActionError(null)
    try {
      await occupantsService.archive(id)
      addToast('Occupant archived successfully.', { type: 'success' })
      setArchiveOpen(false)
      refetch()
    } catch (err) {
      setActionError(err.message)
      setArchiveOpen(false)
    } finally {
      setArchiving(false)
    }
  }

  const handleCheckout = async () => {
    if (!activeOccupancy) return
    setCheckingOut(true)
    setActionError(null)
    try {
      await occupancyService.checkout(activeOccupancy.id)
      addToast(`${occupant.full_name} checked out successfully.`, { type: 'success' })
      setCheckoutOpen(false)
      refetchOcc()
      refetchHist()
    } catch (err) {
      setActionError(err.message)
      setCheckoutOpen(false)
    } finally {
      setCheckingOut(false)
    }
  }

  const handleAssigned = () => {
    // AssignOccupancyDialog already fires its own success toast on a successful
    // assignment — this callback only needs to close the dialog and refresh data.
    setAssignOpen(false)
    refetchOcc()
    refetchHist()
  }

  const handlePaymentRecorded = () => {
    // RecordPaymentDialog already fires its own success toast on a successful
    // payment — this callback only needs to close the dialog and refresh data.
    setRecordPmtOpen(false)
    refetchBal()
    refetchPmt()
  }

  useEffect(() => {
    if (occupant?.is_active && searchParams.get('recordPayment')) {
      setRecordPmtOpen(true)
      const next = new URLSearchParams(searchParams)
      next.delete('recordPayment')
      setSearchParams(next, { replace: true })
    }
  }, [occupant, searchParams, setSearchParams])

  if (loading) {
    return (
      <PageContainer title="Occupant Details" description="Loading occupant information...">
        <Card>
          <Skeleton className="h-8 w-1/3 mb-4" />
          <Skeleton className="h-4 w-1/2 mb-2" />
          <Skeleton className="h-4 w-2/3" />
        </Card>
      </PageContainer>
    )
  }

  if (error) {
    return (
      <PageContainer title="Occupant Details" description="Something went wrong.">
        <Card>
          <div className="text-center py-8">
            <p className="text-red-600 mb-4">{error}</p>
            <Button variant="secondary" onClick={refetch}>Try Again</Button>
          </div>
        </Card>
      </PageContainer>
    )
  }

  if (!occupant) return null

  const fields = [
    { label: 'First Name', value: occupant.first_name },
    { label: 'Last Name', value: occupant.last_name },
    { label: 'Email', value: occupant.email || '—' },
    { label: 'Phone', value: occupant.phone || '—' },
    { label: 'Student ID', value: occupant.student_id_number || '—' },
    { label: 'National ID', value: occupant.national_id || '—' },
    { label: 'Status', value: occupant.is_active ? 'Active' : 'Archived' },
    { label: 'Registered', value: new Date(occupant.created_at).toLocaleDateString() },
  ]

  const balanceNum = balance ? Number(balance.balance) : 0
  const totalPaid = balance ? Number(balance.total_paid) : 0
  const totalCharges = balance ? Number(balance.total_charges) : 0

  return (
    <PageContainer title="Occupant Details" description={`Profile for ${occupant.full_name}`}>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <Card>
            <dl className="grid grid-cols-1 sm:grid-cols-2 gap-6">
              {fields.map((field) => (
                <div key={field.label}>
                  <dt className="text-sm font-medium text-gray-500">{field.label}</dt>
                  <dd className="mt-1 text-sm text-gray-900">{field.value}</dd>
                </div>
              ))}
            </dl>
          </Card>

          <Card title="Current Assignment">
            {occLoading ? (
              <Skeleton className="h-12 w-full" />
            ) : activeOccupancy ? (
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                <div className="space-y-1">
                  <p className="text-sm text-gray-900">
                    <span className="font-medium">{activeOccupancy.unit_name}</span>
                    {' '}&mdash;{' '}
                    <span className="text-gray-500">{activeOccupancy.property_name}</span>
                  </p>
                  <p className="text-xs text-gray-500">
                    Since {new Date(activeOccupancy.start_date).toLocaleDateString()}
                    {' '}&middot;{' '}
                    {activeOccupancy.billing_mode === 'semester' ? 'Semester' : 'Monthly'} billing
                  </p>
                </div>
                <Button
                  variant="secondary"
                  className="text-red-600 border-red-200 hover:bg-red-50 shrink-0"
                  onClick={() => setCheckoutOpen(true)}
                >
                  Check Out
                </Button>
              </div>
            ) : (
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                <p className="text-gray-500 text-sm">Not currently assigned to any unit.</p>
                {occupant.is_active && (
                  <Button onClick={() => setAssignOpen(true)}>
                    Assign to Unit
                  </Button>
                )}
              </div>
            )}
          </Card>

          <Card title="Payment Summary">
            {balLoading ? (
              <CardSkeleton count={1} height="h-16" />
            ) : (
              <div className="grid grid-cols-3 gap-4">
                <div className="text-center p-4 bg-gray-50 rounded-lg">
                  <p className="text-sm text-gray-500">Amount Due</p>
                  <p className="text-xl font-bold text-gray-900 mt-1">
                    {formatUGX(totalCharges)}
                  </p>
                </div>
                <div className="text-center p-4 bg-emerald-50 rounded-lg">
                  <p className="text-sm text-gray-500">Total Paid</p>
                  <p className="text-xl font-bold text-emerald-600 mt-1">
                    {formatUGX(totalPaid)}
                  </p>
                </div>
                <div className="text-center p-4 bg-red-50 rounded-lg">
                  <p className="text-sm text-gray-500">Outstanding</p>
                  <p className={`text-xl font-bold mt-1 ${balanceNum > 0 ? 'text-red-600' : 'text-gray-900'}`}>
                    {formatUGX(balanceNum)}
                  </p>
                </div>
              </div>
            )}
          </Card>

          <Card title="Payment History">
            {pmtLoading ? (
              <TableSkeleton rows={3} cols={5} />
            ) : !payments || payments.length === 0 ? (
              <EmptyState
                icon="currency"
                title="No payments yet"
                description="Payments recorded for this occupant will appear here."
                action={
                  occupant.is_active ? (
                    <Button size="sm" onClick={() => setRecordPmtOpen(true)}>
                      Record Payment
                    </Button>
                  ) : null
                }
              />
            ) : (
              <div className="overflow-x-auto -mx-6">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-gray-500 border-b border-gray-200">
                      <th className="pb-2 px-6 font-medium">Date</th>
                      <th className="pb-2 px-6 font-medium">Amount</th>
                      <th className="pb-2 px-6 font-medium">Method</th>
                      <th className="pb-2 px-6 font-medium hidden sm:table-cell">Reference</th>
                      <th className="pb-2 px-6 font-medium hidden md:table-cell">Notes</th>
                    </tr>
                  </thead>
                  <tbody>
                    {payments.map((p) => (
                      <tr key={p.id} className="border-b border-gray-100">
                        <td className="py-2.5 px-6 text-gray-700 whitespace-nowrap">
                          {new Date(p.payment_date).toLocaleDateString()}
                        </td>
                        <td className="py-2.5 px-6 text-gray-900 font-medium whitespace-nowrap">
                          {formatUGX(p.amount)}
                        </td>
                        <td className="py-2.5 px-6 text-gray-500 whitespace-nowrap">
                          {methodLabels[p.payment_method] || p.payment_method}
                        </td>
                        <td className="py-2.5 px-6 text-gray-500 hidden sm:table-cell">{p.reference || '—'}</td>
                        <td className="py-2.5 px-6 text-gray-500 max-w-[120px] truncate hidden md:table-cell">
                          {p.notes || '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          <Card title="Occupancy History">
            {histLoading ? (
              <TableSkeleton rows={3} cols={6} />
            ) : !history || history.length === 0 ? (
              <EmptyState
                icon="building"
                title="No occupancy records"
                description="This occupant has not been assigned to any unit yet."
              />
            ) : (
              <div className="overflow-x-auto -mx-6">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-gray-500 border-b border-gray-200">
                      <th className="pb-2 px-6 font-medium">Unit</th>
                      <th className="pb-2 px-6 font-medium">Property</th>
                      <th className="pb-2 px-6 font-medium hidden sm:table-cell">Start Date</th>
                      <th className="pb-2 px-6 font-medium hidden sm:table-cell">End Date</th>
                      <th className="pb-2 px-6 font-medium hidden md:table-cell">Billing</th>
                      <th className="pb-2 px-6 font-medium">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {history.map((occ) => (
                      <tr key={occ.id} className="border-b border-gray-100">
                        <td className="py-2.5 px-6 text-gray-900 whitespace-nowrap">{occ.unit_name}</td>
                        <td className="py-2.5 px-6 text-gray-500 whitespace-nowrap">{occ.property_name}</td>
                        <td className="py-2.5 px-6 text-gray-700 whitespace-nowrap hidden sm:table-cell">
                          {new Date(occ.start_date).toLocaleDateString()}
                        </td>
                        <td className="py-2.5 px-6 text-gray-700 whitespace-nowrap hidden sm:table-cell">
                          {occ.end_date ? new Date(occ.end_date).toLocaleDateString() : '—'}
                        </td>
                        <td className="py-2.5 px-6 text-gray-700 whitespace-nowrap hidden md:table-cell capitalize">
                          {occ.billing_mode}
                        </td>
                        <td className="py-2.5 px-6">
                          <span
                            className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                              occ.is_active
                                ? 'bg-emerald-100 text-emerald-700'
                                : 'bg-gray-100 text-gray-600'
                            }`}
                          >
                            {occ.is_active ? 'Active' : 'Past'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>

        <div className="space-y-4">
          <Card>
            <h3 className="text-sm font-medium text-gray-500 mb-3">Actions</h3>
            <div className="space-y-3">
              {occupant.is_active && (
                <Button className="w-full" onClick={() => setRecordPmtOpen(true)}>
                  Record Payment
                </Button>
              )}
              {!activeOccupancy && occupant.is_active && (
                <Button
                  variant="secondary"
                  className="w-full"
                  onClick={() => setAssignOpen(true)}
                >
                  Assign to Unit
                </Button>
              )}
              <Link to={`/occupants/${id}/edit`}>
                <Button variant="secondary" className="w-full">Edit Occupant</Button>
              </Link>
              {occupant.is_active && (
                <Button
                  variant="secondary"
                  className="w-full text-red-600 hover:text-red-700 hover:bg-red-50 border-red-200"
                  onClick={() => setArchiveOpen(true)}
                  disabled={archiving}
                >
                  {archiving ? 'Archiving...' : 'Archive Occupant'}
                </Button>
              )}
              <Link to="/occupants">
                <Button variant="ghost" className="w-full">&larr; Back to List</Button>
              </Link>
            </div>
          </Card>

          {actionError && (
            <Card className="border-red-200 bg-red-50">
              <p className="text-sm text-red-700">{actionError}</p>
            </Card>
          )}
        </div>
      </div>

      <ConfirmDialog
        open={archiveOpen}
        title="Archive Occupant"
        message={`Are you sure you want to archive ${occupant.full_name}? They will no longer appear in the active occupants list, but their records will be preserved.`}
        confirmLabel="Archive"
        onConfirm={handleArchive}
        onCancel={() => setArchiveOpen(false)}
      />

      <ConfirmDialog
        open={checkoutOpen}
        title="Check Out Occupant"
        message={`Confirm that ${occupant.full_name} is checking out of ${activeOccupancy?.unit_name} (${activeOccupancy?.property_name}). This will free up the unit and end the current occupancy as of today.`}
        confirmLabel={checkingOut ? 'Checking Out...' : 'Confirm Check Out'}
        onConfirm={handleCheckout}
        onCancel={() => setCheckoutOpen(false)}
      />

      <AssignOccupancyDialog
        open={assignOpen}
        occupant={occupant}
        onClose={() => setAssignOpen(false)}
        onAssigned={handleAssigned}
      />

      <RecordPaymentDialog
        open={recordPmtOpen}
        occupant={occupant}
        onClose={() => setRecordPmtOpen(false)}
        onRecorded={handlePaymentRecorded}
      />
    </PageContainer>
  )
}

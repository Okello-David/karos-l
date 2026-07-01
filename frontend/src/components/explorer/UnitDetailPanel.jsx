import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useUnitDetail } from '../../hooks/useExplorer'
import Spinner from '../Spinner'

function CloseIcon() {
  return (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
    </svg>
  )
}

function formatUGX(amount) {
  const num = parseFloat(amount)
  if (isNaN(num)) return '—'
  return 'UGX ' + num.toLocaleString('en-UG', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function formatDate(dateStr) {
  if (!dateStr) return 'Present'
  return new Date(dateStr).toLocaleDateString('en-UG', {
    day: 'numeric', month: 'short', year: 'numeric',
  })
}

export default function UnitDetailPanel({ unitId, onClose }) {
  const navigate = useNavigate()
  const { data: unit, loading, error } = useUnitDetail(unitId)
  const panelRef = useRef(null)

  useEffect(() => {
    if (unitId && panelRef.current) {
      panelRef.current.focus()
    }
  }, [unitId])

  if (!unitId) return null

  return (
    <>
      <div
        className="fixed inset-0 bg-black/20 z-40 lg:hidden"
        onClick={onClose}
      />

      <div
        ref={panelRef}
        tabIndex={-1}
        className="fixed inset-y-0 right-0 w-full max-w-lg bg-white border-l border-gray-200 shadow-xl z-50 flex flex-col outline-none lg:relative lg:inset-auto lg:z-auto lg:max-w-md lg:border lg:rounded-xl lg:shadow-sm"
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">
              {loading ? 'Loading...' : unit?.name || 'Unit Details'}
            </h2>
            {unit && (
              <p className="text-sm text-gray-500">
                {unit.property_name} / {unit.section_name}
              </p>
            )}
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
            aria-label="Close panel"
          >
            <CloseIcon />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-4">
          {loading && (
            <div className="flex justify-center py-12">
              <Spinner />
            </div>
          )}

          {error && (
            <div className="p-4 bg-red-50 text-red-700 rounded-lg text-sm">
              {error}
            </div>
          )}

          {unit && !loading && (
            <div className="space-y-6">
              {/* Unit Info */}
              <section>
                <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
                  Unit Information
                </h3>
                <dl className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <dt className="text-gray-500">Capacity</dt>
                    <dd className="font-medium text-gray-900">{unit.capacity}</dd>
                  </div>
                  <div>
                    <dt className="text-gray-500">Occupied</dt>
                    <dd className="font-medium text-gray-900">{unit.current_occupant_count}</dd>
                  </div>
                  <div>
                    <dt className="text-gray-500">Available</dt>
                    <dd className="font-medium text-gray-900">{unit.available_spaces}</dd>
                  </div>
                  <div>
                    <dt className="text-gray-500">Status</dt>
                    <dd className={`font-medium ${unit.is_full ? 'text-red-600' : unit.available_spaces === 0 ? 'text-yellow-600' : 'text-green-600'}`}>
                      {unit.is_full ? 'Full' : unit.available_spaces > 0 ? 'Available' : 'Nearly Full'}
                    </dd>
                  </div>
                  <div className="col-span-2">
                    <dt className="text-gray-500">Semester Price</dt>
                    <dd className="font-medium text-gray-900">{formatUGX(unit.semester_price)}</dd>
                  </div>
                  <div className="col-span-2">
                    <dt className="text-gray-500">Monthly Price</dt>
                    <dd className="font-medium text-gray-900">{formatUGX(unit.monthly_price)}</dd>
                  </div>
                </dl>
              </section>

              {/* Current Occupants */}
              <section>
                <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
                  Current Occupants
                </h3>
                {unit.current_occupants?.length > 0 ? (
                  <div className="space-y-3">
                    {unit.current_occupants.map((occ) => (
                      <div
                        key={occ.id}
                        className="p-3 bg-gray-50 rounded-lg"
                      >
                        <div className="flex items-center justify-between mb-2">
                          <span className="font-medium text-gray-900 text-sm">{occ.name}</span>
                          {occ.has_balance && (
                            <span className="text-xs font-medium text-red-600 bg-red-50 px-2 py-0.5 rounded-full">
                              {formatUGX(occ.balance)}
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-4 text-xs text-gray-500">
                          <span>Since {formatDate(occ.start_date)}</span>
                          <span className="capitalize">{occ.billing_mode}</span>
                        </div>
                        <div className="flex gap-2 mt-2">
                          <button
                            onClick={() => navigate(`/occupants/${occ.id}`)}
                            className="text-xs text-primary-600 hover:text-primary-700 font-medium"
                          >
                            View Occupant
                          </button>
                          <button
                            onClick={() => navigate(`/occupants/${occ.id}`)}
                            className="text-xs text-primary-600 hover:text-primary-700 font-medium"
                          >
                            Record Payment
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-sm text-gray-400 bg-gray-50 rounded-lg p-4 text-center">
                    No current occupants
                    {unit.available_spaces > 0 && (
                      <p className="mt-1">
                        <button
                          onClick={() => navigate('/occupants')}
                          className="text-primary-600 hover:text-primary-700 font-medium"
                        >
                          Assign Occupant
                        </button>
                      </p>
                    )}
                  </div>
                )}
              </section>

              {/* Quick Actions */}
              <section>
                <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
                  Quick Actions
                </h3>
                <div className="flex flex-wrap gap-2">
                  {unit.available_spaces > 0 && (
                    <button
                      onClick={() => navigate('/occupants')}
                      className="px-3 py-2 text-sm font-medium text-primary-700 bg-primary-50 rounded-lg hover:bg-primary-100 transition-colors"
                    >
                      Assign Occupant
                    </button>
                  )}
                  {unit.current_occupants?.length > 0 && (
                    <button
                      onClick={() => navigate('/payments')}
                      className="px-3 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
                    >
                      View Payments
                    </button>
                  )}
                </div>
              </section>

              {/* Occupancy History */}
              <section>
                <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
                  Occupancy History
                </h3>
                {unit.occupancy_history?.length > 0 ? (
                  <div className="space-y-2">
                    {unit.occupancy_history.map((hist) => (
                      <div
                        key={hist.id}
                        className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0"
                      >
                        <div>
                          <span className="text-sm text-gray-900">{hist.student_name}</span>
                          <p className="text-xs text-gray-500">
                            {formatDate(hist.start_date)} — {formatDate(hist.end_date)}
                          </p>
                        </div>
                        {hist.is_active && (
                          <span className="text-xs font-medium text-green-600 bg-green-50 px-2 py-0.5 rounded-full">
                            Active
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-gray-400 bg-gray-50 rounded-lg p-4 text-center">
                    No occupancy history
                  </p>
                )}
              </section>
            </div>
          )}
        </div>
      </div>
    </>
  )
}

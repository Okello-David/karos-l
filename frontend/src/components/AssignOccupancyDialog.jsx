import { useState, useEffect } from 'react'
import Button from './Button'
import Spinner from './Spinner'
import EmptyState from './EmptyState'
import { propertyService, sectionService, unitService } from '../services/properties'
import { occupancyService } from '../services/occupancy'
import { useToast } from './Toast'

const STEPS = [
  { num: 1, title: 'Select Property' },
  { num: 2, title: 'Select Section' },
  { num: 3, title: 'Select Unit' },
]

export default function AssignOccupancyDialog({ open, occupant, onClose, onAssigned }) {
  const { addToast } = useToast()
  const [step, setStep] = useState(1)
  const [properties, setProperties] = useState([])
  const [sections, setSections] = useState([])
  const [units, setUnits] = useState([])
  const [selectedProperty, setSelectedProperty] = useState(null)
  const [selectedSection, setSelectedSection] = useState(null)
  const [selectedUnit, setSelectedUnit] = useState(null)
  const [startDate, setStartDate] = useState(new Date().toISOString().split('T')[0])
  const [billingMode, setBillingMode] = useState('semester')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)
  const [loadingSections, setLoadingSections] = useState(false)
  const [loadingUnits, setLoadingUnits] = useState(false)

  useEffect(() => {
    if (!open) return
    setStep(1)
    setSelectedProperty(null)
    setSelectedSection(null)
    setSelectedUnit(null)
    setStartDate(new Date().toISOString().split('T')[0])
    setBillingMode('semester')
    setError(null)
    propertyService.list()
      .then(setProperties)
      .catch(() => {})
  }, [open])

  useEffect(() => {
    if (!selectedProperty) return
    setSelectedSection(null)
    setSelectedUnit(null)
    setLoadingSections(true)
    sectionService.list(selectedProperty.id)
      .then((data) => { setSections(data); setLoadingSections(false) })
      .catch(() => setLoadingSections(false))
  }, [selectedProperty])

  useEffect(() => {
    if (!selectedSection) return
    setSelectedUnit(null)
    setLoadingUnits(true)
    unitService.list(selectedSection.id)
      .then((data) => { setUnits(data); setLoadingUnits(false) })
      .catch(() => setLoadingUnits(false))
  }, [selectedSection])

  const handlePropertySelect = (prop) => {
    setSelectedProperty(prop)
    setStep(2)
  }

  const handleSectionSelect = (sec) => {
    setSelectedSection(sec)
    setStep(3)
  }

  const handleUnitSelect = (unit) => {
    setSelectedUnit(unit)
  }

  const handleSubmit = async () => {
    if (!selectedUnit) return
    setSubmitting(true)
    setError(null)
    try {
      await occupancyService.assign({
        student: occupant.id,
        unit: selectedUnit.id,
        start_date: startDate,
        billing_mode: billingMode,
      })
      addToast(`${occupant.full_name} assigned to ${selectedUnit.name} successfully.`, { type: 'success' })
      onAssigned()
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  const handleBack = () => {
    if (step > 1) setStep(step - 1)
  }

  if (!open) return null

  const currentStep = STEPS.find((s) => s.num === step)

  const listItemClass = (selected = false, disabled = false) =>
    `w-full text-left px-4 py-3 rounded-lg border transition-colors ${
      selected
        ? 'border-primary-500 bg-primary-50'
        : disabled
          ? 'border-gray-100 bg-gray-50 text-gray-400 cursor-not-allowed'
          : 'border-gray-200 hover:border-primary-300 hover:bg-primary-50'
    }`

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="fixed inset-0 bg-black/40" onClick={onClose} aria-hidden="true" />
      <div
        className="relative bg-white rounded-xl shadow-xl max-w-lg w-full p-6 space-y-5"
        role="dialog"
        aria-modal="true"
        aria-labelledby="assign-title"
      >
        <div className="flex items-center justify-between">
          <div>
            {step > 1 && (
              <button
                onClick={handleBack}
                className="text-sm text-gray-500 hover:text-gray-700 mr-3"
                aria-label="Back"
              >
                &larr; Back
              </button>
            )}
            <h2 id="assign-title" className="text-lg font-semibold text-gray-900 inline">
              Assign Unit
            </h2>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-xl leading-none"
            aria-label="Close"
          >
            &times;
          </button>
        </div>

        <div className="flex items-center gap-3">
          {STEPS.map((s) => (
            <span
              key={s.num}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs ${
                s.num === step
                  ? 'bg-primary-100 text-primary-700 font-semibold'
                  : s.num < step
                    ? 'bg-emerald-100 text-emerald-700'
                    : 'bg-gray-100 text-gray-400'
              }`}
            >
              {s.num < step ? (
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                </svg>
              ) : (
                <span>{s.num}.</span>
              )}
              {s.title}
            </span>
          ))}
        </div>

        {/* Step 1: Property */}
        {step === 1 && (
          <div>
            <p className="text-sm font-medium text-gray-700 mb-3">Choose a property for {occupant?.full_name}:</p>
            <div className="space-y-2 max-h-60 overflow-y-auto">
              {properties.length === 0 ? (
                <p className="text-gray-500 text-sm text-center py-8">No properties available.</p>
              ) : (
                properties.map((prop) => (
                  <button
                    key={prop.id}
                    onClick={() => handlePropertySelect(prop)}
                    className={listItemClass(false)}
                  >
                    <span className="font-medium text-gray-900">{prop.name}</span>
                    {prop.code && <span className="ml-2 text-xs text-gray-400 font-mono">{prop.code}</span>}
                  </button>
                ))
              )}
            </div>
          </div>
        )}

        {/* Step 2: Section */}
        {step === 2 && (
          <div>
            <p className="text-sm font-medium text-gray-700 mb-3">
              Sections in <span className="text-primary-600">{selectedProperty?.name}</span>:
            </p>
            <div className="space-y-2 max-h-60 overflow-y-auto">
              {loadingSections ? (
                <div className="flex justify-center py-8"><Spinner size="sm" label="Loading sections..." /></div>
              ) : sections.length === 0 ? (
                <EmptyState icon="building" title="No sections" description="This property has no sections." />
              ) : (
                sections.map((sec) => (
                  <button
                    key={sec.id}
                    onClick={() => handleSectionSelect(sec)}
                    className={listItemClass(false)}
                  >
                    <span className="font-medium text-gray-900">{sec.name}</span>
                  </button>
                ))
              )}
            </div>
          </div>
        )}

        {/* Step 3: Unit */}
        {step === 3 && (
          <div>
            <p className="text-sm font-medium text-gray-700 mb-3">
              Units in <span className="text-primary-600">{selectedSection?.name}</span>:
            </p>
            <div className="space-y-2 max-h-60 overflow-y-auto">
              {loadingUnits ? (
                <div className="flex justify-center py-8"><Spinner size="sm" label="Loading units..." /></div>
              ) : units.length === 0 ? (
                <EmptyState icon="building" title="No units" description="This section has no units." />
              ) : (
                units.map((unit) => {
                  const full = unit.is_full
                  return (
                    <button
                      key={unit.id}
                      onClick={() => handleUnitSelect(unit)}
                      disabled={full}
                      className={listItemClass(selectedUnit?.id === unit.id, full)}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-medium">{unit.name}</span>
                        <span className={`text-sm ${full ? 'text-red-400' : 'text-gray-500'}`}>
                          {unit.current_occupant_count}/{unit.capacity}
                          {unit.available_spaces > 0
                            ? ` (${unit.available_spaces} free)`
                            : ' (Full)'}
                        </span>
                      </div>
                    </button>
                  )
                })
              )}
            </div>
          </div>
        )}

        {/* Confirmation Section (Step 3, unit selected) */}
        {step === 3 && selectedUnit && (
          <div className="border-t border-gray-200 pt-4 space-y-4">
            <p className="text-sm font-semibold text-gray-900">Confirm Assignment</p>

            <div className="grid grid-cols-2 gap-3 text-sm bg-gray-50 rounded-lg p-4">
              <div>
                <p className="text-gray-500 text-xs">Occupant</p>
                <p className="font-medium text-gray-900">{occupant?.full_name}</p>
              </div>
              <div>
                <p className="text-gray-500 text-xs">Unit</p>
                <p className="font-medium text-gray-900">{selectedUnit.name}</p>
              </div>
              <div>
                <p className="text-gray-500 text-xs">Property</p>
                <p className="font-medium text-gray-900">{selectedProperty?.name}</p>
              </div>
              <div>
                <p className="text-gray-500 text-xs">Section</p>
                <p className="font-medium text-gray-900">{selectedSection?.name}</p>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label htmlFor="start-date" className="block text-sm font-medium text-gray-700 mb-1">
                  Start Date
                </label>
                <input
                  id="start-date"
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                />
              </div>
              <div>
                <label htmlFor="billing-mode" className="block text-sm font-medium text-gray-700 mb-1">
                  Billing Mode
                </label>
                <select
                  id="billing-mode"
                  value={billingMode}
                  onChange={(e) => setBillingMode(e.target.value)}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                >
                  <option value="semester">Semester</option>
                  <option value="monthly">Monthly</option>
                </select>
              </div>
            </div>

            {error && (
              <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                {error}
              </p>
            )}

            <div className="flex justify-end gap-3">
              <Button variant="secondary" onClick={onClose}>Cancel</Button>
              <Button onClick={handleSubmit} disabled={submitting || !selectedUnit}>
                {submitting ? 'Assigning...' : 'Assign Unit'}
              </Button>
            </div>
          </div>
        )}

        {step < 3 && (
          <div className="flex justify-end pt-2">
            <Button variant="secondary" onClick={onClose}>Cancel</Button>
          </div>
        )}
      </div>
    </div>
  )
}

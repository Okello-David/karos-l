import { useState } from 'react'
import Spinner from './Spinner'
import { useOccupants } from '../hooks/useOccupants'

export default function OccupantPickerDialog({ onClose, onSelect }) {
  const [search, setSearch] = useState('')
  const { data, loading } = useOccupants({ search, status: 'active', page_size: 20 })

  const handleClose = () => {
    setSearch('')
    onClose()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="fixed inset-0 bg-black/40" onClick={handleClose} aria-hidden="true" />
      <div
        className="relative bg-white rounded-xl shadow-xl max-w-lg w-full p-6 space-y-4"
        role="dialog"
        aria-modal="true"
        aria-labelledby="occupant-picker-title"
      >
        <div className="flex items-center justify-between">
          <h2 id="occupant-picker-title" className="text-lg font-semibold text-gray-900">
            Record Payment
          </h2>
          <button
            onClick={handleClose}
            className="text-gray-400 hover:text-gray-600 text-xl leading-none"
            aria-label="Close"
          >
            &times;
          </button>
        </div>

        <div>
          <label htmlFor="occupant-picker-search" className="block text-sm font-medium text-gray-700 mb-1">
            Choose an occupant to record a payment for
          </label>
          <input
            id="occupant-picker-search"
            type="text"
            autoFocus
            placeholder="Search by name, phone, ID..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        </div>

        <div className="space-y-2 max-h-72 overflow-y-auto">
          {loading ? (
            <div className="flex justify-center py-8"><Spinner size="sm" label="Loading occupants..." /></div>
          ) : !data?.results?.length ? (
            <p className="text-gray-500 text-sm text-center py-8">
              {search ? 'No occupants match your search.' : 'No active occupants found.'}
            </p>
          ) : (
            data.results.map((occupant) => (
              <button
                key={occupant.id}
                onClick={() => onSelect(occupant)}
                className="w-full text-left px-4 py-3 rounded-lg border border-gray-200 hover:border-primary-300 hover:bg-primary-50 transition-colors"
              >
                <span className="font-medium text-gray-900">{occupant.full_name}</span>
                {occupant.email && <span className="ml-2 text-xs text-gray-400">{occupant.email}</span>}
              </button>
            ))
          )}
        </div>
      </div>
    </div>
  )
}

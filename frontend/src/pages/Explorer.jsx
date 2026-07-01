import { useState, useCallback } from 'react'
import PageContainer from '../components/PageContainer'
import Spinner from '../components/Spinner'
import EmptyState from '../components/EmptyState'
import PropertyNode from '../components/explorer/PropertyNode'
import UnitDetailPanel from '../components/explorer/UnitDetailPanel'
import { useExplorer } from '../hooks/useExplorer'

function SearchIcon() {
  return (
    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
    </svg>
  )
}

export default function Explorer() {
  const [search, setSearch] = useState('')
  const [selectedUnitId, setSelectedUnitId] = useState(null)
  const { data: properties, loading, error } = useExplorer(search)

  const handleSearch = useCallback((value) => {
    setSearch(value)
    setSelectedUnitId(null)
  }, [])

  const handleSelectUnit = useCallback((unitId) => {
    setSelectedUnitId((prev) => (prev === unitId ? null : unitId))
  }, [])

  const handleClosePanel = useCallback(() => {
    setSelectedUnitId(null)
  }, [])

  return (
    <PageContainer
      title="Property Explorer"
      description="Browse properties, sections, and units to view occupancy status and details."
    >
      {/* Search */}
      <div className="mb-6">
        <div className="relative max-w-md">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
            <SearchIcon />
          </div>
          <input
            type="text"
            value={search}
            onChange={(e) => handleSearch(e.target.value)}
            placeholder="Search units or occupants..."
            className="block w-full pl-10 pr-4 py-2.5 border border-gray-300 rounded-xl text-sm bg-white focus:ring-2 focus:ring-primary-500 focus:border-primary-500 outline-none transition-shadow"
          />
          {search && (
            <button
              onClick={() => handleSearch('')}
              className="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-400 hover:text-gray-600"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>
      </div>

      {/* Loading */}
      {loading && (
        <div className="flex justify-center py-20">
          <Spinner />
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="p-4 bg-red-50 text-red-700 rounded-xl text-sm mb-6">
          {error}
        </div>
      )}

      {/* Content */}
      {!loading && !error && (
        <div className="flex flex-col lg:flex-row gap-6">
          {/* Tree */}
          <div className="flex-1 min-w-0 space-y-4">
            {!properties || properties.length === 0 ? (
              <EmptyState
                icon={search ? 'search' : 'building'}
                title={search ? 'No matching results' : 'No properties yet'}
                description={search ? 'Try a different search term.' : 'Properties will appear here once they are configured.'}
              />
            ) : (
              properties.map((property) => (
                <PropertyNode
                  key={property.id}
                  property={property}
                  defaultOpen={properties.length === 1}
                  onSelectUnit={handleSelectUnit}
                />
              ))
            )}
          </div>

          {/* Detail Panel - Desktop side panel */}
          <div className="hidden lg:block lg:w-96 xl:w-[420px] flex-shrink-0">
            {selectedUnitId ? (
              <UnitDetailPanel
                unitId={selectedUnitId}
                onClose={handleClosePanel}
              />
            ) : (
              <div className="border border-dashed border-gray-300 rounded-xl p-8 text-center">
                <svg className="w-10 h-10 mx-auto text-gray-300 mb-3" fill="none" viewBox="0 0 24 24" strokeWidth={1} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                </svg>
                <p className="text-sm text-gray-500">Select a unit to view details</p>
              </div>
            )}
          </div>

          {/* Detail Panel - Mobile/Tablet modal */}
          <div className="lg:hidden">
            {selectedUnitId && (
              <UnitDetailPanel
                unitId={selectedUnitId}
                onClose={handleClosePanel}
              />
            )}
          </div>
        </div>
      )}
    </PageContainer>
  )
}

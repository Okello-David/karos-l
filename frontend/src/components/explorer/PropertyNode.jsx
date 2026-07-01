import { useState } from 'react'
import SectionNode from './SectionNode'

function ChevronIcon({ open }) {
  return (
    <svg
      className={`w-5 h-5 transition-transform ${open ? 'rotate-90' : ''}`}
      fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor"
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
    </svg>
  )
}

function BuildingIcon() {
  return (
    <svg className="w-5 h-5 text-gray-400" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 21h16.5M4.5 3h15M5.25 3v18m13.5-18v18M9 6.75h1.5m-1.5 3h1.5m-1.5 3h1.5m3-6H15m-1.5 3H15m-1.5 3H15M9 21v-3.375c0-.621.504-1.125 1.125-1.125h3.75c.621 0 1.125.504 1.125 1.125V21" />
    </svg>
  )
}

function countUnits(sections) {
  return sections.reduce((sum, s) => sum + (s.units?.length || 0), 0)
}

export default function PropertyNode({ property, defaultOpen = false, onSelectUnit }) {
  const [open, setOpen] = useState(defaultOpen)
  const sections = property.sections || []
  const unitCount = countUnits(sections)

  return (
    <div className="border border-gray-200 rounded-xl bg-white overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-3 px-5 py-4 text-left hover:bg-gray-50 transition-colors"
      >
        <ChevronIcon open={open} />
        <BuildingIcon />
        <div className="flex-1 min-w-0">
          <span className="font-semibold text-gray-900">{property.name}</span>
          {property.code && (
            <span className="ml-2 text-xs text-gray-400 font-mono">{property.code}</span>
          )}
        </div>
        <span className="text-sm text-gray-500 whitespace-nowrap">
          {unitCount} {unitCount === 1 ? 'unit' : 'units'}
        </span>
      </button>

      {open && (
        <div className="border-t border-gray-100">
          {sections.length === 0 ? (
            <p className="px-5 py-6 text-sm text-gray-400 text-center">No sections</p>
          ) : (
            <div className="divide-y divide-gray-50">
              {sections.map((section) => (
                <SectionNode key={section.id} section={section} onSelectUnit={onSelectUnit} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

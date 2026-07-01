import { useState } from 'react'
import UnitNode from './UnitNode'

function ChevronIcon({ open }) {
  return (
    <svg
      className={`w-4 h-4 transition-transform ${open ? 'rotate-90' : ''}`}
      fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor"
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
    </svg>
  )
}

function FolderIcon() {
  return (
    <svg className="w-4 h-4 text-gray-400" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z" />
    </svg>
  )
}

export default function SectionNode({ section, onSelectUnit }) {
  const [open, setOpen] = useState(false)
  const units = section.units || []

  return (
    <div className="pl-4">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2 px-4 py-3 text-left hover:bg-gray-50 transition-colors"
      >
        <ChevronIcon open={open} />
        <FolderIcon />
        <span className="text-sm font-medium text-gray-700">{section.name}</span>
        <span className="text-xs text-gray-400">
          {units.filter((u) => u.is_full).length}/{units.length} full
        </span>
      </button>

      {open && (
        <div className="pb-3 px-4">
          {units.length === 0 ? (
            <p className="py-4 text-sm text-gray-400 text-center">No units</p>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3 mt-2">
              {units.map((unit) => (
                <UnitNode key={unit.id} unit={unit} onSelect={onSelectUnit} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

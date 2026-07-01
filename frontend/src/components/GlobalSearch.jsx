import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../services/api'
import Spinner from './Spinner'

export default function GlobalSearch({ open, onClose }) {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [results, setResults] = useState({ occupants: [], receipts: [], properties: [] })
  const [loading, setLoading] = useState(false)
  const [activeIndex, setActiveIndex] = useState(-1)
  const inputRef = useRef(null)

  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 50)
      setQuery('')
      setResults({ occupants: [], receipts: [], properties: [] })
      setActiveIndex(-1)
    }
  }, [open])

  useEffect(() => {
    if (!query.trim()) {
      setResults({ occupants: [], receipts: [], properties: [] })
      setLoading(false)
      return
    }

    const timer = setTimeout(async () => {
      setLoading(true)
      try {
        const [occupantsRes, receiptsRes, explorerRes] = await Promise.allSettled([
          api.get(`/occupants/?search=${encodeURIComponent(query)}&page_size=5`),
          api.get(`/payments/receipts/?search=${encodeURIComponent(query)}&page_size=5`),
          api.get(`/properties/explorer/?search=${encodeURIComponent(query)}`),
        ])

        setResults({
          occupants: occupantsRes.status === 'fulfilled' ? occupantsRes.value.results || [] : [],
          receipts: receiptsRes.status === 'fulfilled' ? receiptsRes.value.results || [] : [],
          properties: explorerRes.status === 'fulfilled' ? explorerRes.value || [] : [],
        })
      } catch {
        setResults({ occupants: [], receipts: [], properties: [] })
      }
      setLoading(false)
    }, 300)

    return () => clearTimeout(timer)
  }, [query])

  const allItems = [
    ...results.occupants.map((o) => ({ type: 'occupant', id: o.id, label: o.full_name, sub: o.student_id_number, route: `/occupants/${o.id}` })),
    ...results.receipts.map((r) => ({ type: 'receipt', id: r.id, label: r.receipt_number, sub: r.student_name, route: `/receipts` })),
    ...results.properties.map((p) => ({ type: 'property', id: p.id, label: p.name, sub: p.code, route: `/explorer` })),
  ]

  const handleKeyDown = (e) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActiveIndex((i) => Math.min(i + 1, allItems.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActiveIndex((i) => Math.max(i - 1, 0))
    } else if (e.key === 'Enter' && activeIndex >= 0 && allItems[activeIndex]) {
      navigate(allItems[activeIndex].route)
      onClose()
    } else if (e.key === 'Escape') {
      onClose()
    }
  }

  const handleClick = (item) => {
    navigate(item.route)
    onClose()
  }

  if (!open) return null

  const sections = [
    { key: 'occupants', label: 'Occupants', items: results.occupants.map((o) => ({ ...o, type: 'occupant', route: `/occupants/${o.id}`, label: o.full_name, sub: o.student_id_number })) },
    { key: 'receipts', label: 'Receipts', items: results.receipts.map((r) => ({ ...r, type: 'receipt', route: `/receipts`, label: r.receipt_number, sub: r.student_name })) },
    { key: 'properties', label: 'Properties', items: results.properties.map((p) => ({ ...p, type: 'property', route: `/explorer`, label: p.name, sub: p.code })) },
  ]

  let flatIdx = -1

  return (
    <div
      className="fixed inset-0 z-[80] flex items-start justify-center pt-[15vh] p-4 bg-black/30"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label="Global search"
    >
      <div
        className="bg-white rounded-xl shadow-2xl max-w-xl w-full overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-3 px-4 border-b border-gray-200">
          <svg className="w-5 h-5 text-gray-400 shrink-0" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
          </svg>
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => { setQuery(e.target.value); setActiveIndex(-1) }}
            onKeyDown={handleKeyDown}
            placeholder="Search occupants, receipts, properties..."
            className="flex-1 py-4 text-sm bg-transparent border-0 focus:outline-none focus:ring-0"
            autoComplete="off"
          />
          {loading && <Spinner size="sm" />}
          <kbd className="hidden sm:inline-flex text-xs text-gray-400 font-mono border border-gray-200 rounded px-1.5 py-0.5">ESC</kbd>
        </div>

        {query.trim() && !loading && allItems.length === 0 && (
          <div className="p-8 text-center text-sm text-gray-500">
            No results found for &ldquo;{query}&rdquo;
          </div>
        )}

        {allItems.length > 0 && (
          <div className="max-h-[50vh] overflow-y-auto p-2">
            {sections.map((section) => {
              if (section.items.length === 0) return null
              return (
                <div key={section.key}>
                  <div className="px-3 py-2 text-xs font-semibold text-gray-400 uppercase tracking-wider">
                    {section.label}
                  </div>
                  {section.items.map((item) => {
                    flatIdx++
                    const idx = flatIdx
                    return (
                      <button
                        key={`${item.type}-${item.id}`}
                        onClick={() => handleClick(item)}
                        onMouseEnter={() => setActiveIndex(idx)}
                        className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left transition-colors ${
                          idx === activeIndex ? 'bg-primary-50 text-primary-700' : 'text-gray-700 hover:bg-gray-50'
                        }`}
                      >
                        <span className="text-sm font-medium flex-1 truncate">{item.label}</span>
                        {item.sub && <span className="text-xs text-gray-400 truncate max-w-[180px]">{item.sub}</span>}
                        {item.type === 'occupant' && (
                          <span className="text-xs text-gray-400 shrink-0">Occupant</span>
                        )}
                      </button>
                    )
                  })}
                </div>
              )
            })}
          </div>
        )}

        {query.trim() && (
          <div className="px-4 py-2.5 border-t border-gray-100 text-xs text-gray-400 flex items-center gap-4">
            <span><kbd className="font-mono bg-gray-100 px-1 rounded">&uarr;</kbd> <kbd className="font-mono bg-gray-100 px-1 rounded">&darr;</kbd> Navigate</span>
            <span><kbd className="font-mono bg-gray-100 px-1 rounded">Enter</kbd> Open</span>
            <span><kbd className="font-mono bg-gray-100 px-1 rounded">Esc</kbd> Close</span>
          </div>
        )}
      </div>
    </div>
  )
}

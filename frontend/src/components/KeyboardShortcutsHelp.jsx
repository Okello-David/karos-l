import { useEffect } from 'react'
import Button from './Button'

const defaultShortcuts = [
  { key: 'K', ctrl: true, label: 'Global search' },
  { key: '?', label: 'Toggle keyboard shortcuts' },
  { key: 'Escape', label: 'Close dialog / blur input' },
  { key: 'H', label: 'Go to Home / Dashboard' },
  { key: 'E', label: 'Go to Explorer' },
  { key: 'O', label: 'Go to Occupants' },
  { key: 'P', label: 'Go to Payments' },
  { key: 'R', label: 'Go to Receipts' },
  { key: '/', label: 'Focus search on current page' },
]

export default function KeyboardShortcutsHelp({ open, onClose, customShortcuts = [] }) {
  useEffect(() => {
    if (!open) return
    function handler(e) {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [open, onClose])

  if (!open) return null

  const allShortcuts = [...defaultShortcuts, ...customShortcuts]

  return (
    <div
      className="fixed inset-0 z-[90] flex items-center justify-center p-4 bg-black/30"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label="Keyboard shortcuts"
    >
      <div
        className="bg-white rounded-xl shadow-2xl max-w-lg w-full p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900">Keyboard Shortcuts</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600" aria-label="Close shortcuts">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <div className="divide-y divide-gray-100">
          {allShortcuts.map((s, i) => (
            <div key={i} className="flex items-center justify-between py-2.5">
              <span className="text-sm text-gray-700">{s.label}</span>
              <kbd className="inline-flex items-center gap-1 px-2 py-1 text-xs font-mono bg-gray-100 text-gray-600 rounded">
                {s.ctrl && <span>Ctrl</span>}
                {s.ctrl && s.key && <span>+</span>}
                {s.key === ' ' ? <span>Space</span> : <span>{s.key}</span>}
              </kbd>
            </div>
          ))}
        </div>
        <div className="mt-4 text-center">
          <Button variant="secondary" size="sm" onClick={onClose}>Close</Button>
        </div>
      </div>
    </div>
  )
}

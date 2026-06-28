import { useEffect, useRef } from 'react'
import Button from './Button'

export default function ConfirmDialog({ open, title, message, confirmLabel, onConfirm, onCancel, variant = 'danger' }) {
  const dialogRef = useRef(null)

  useEffect(() => {
    if (!open) return
    const timer = setTimeout(() => {
      const cancelBtn = dialogRef.current?.querySelector('button:first-of-type')
      cancelBtn?.focus()
    }, 50)
    const handleEscape = (e) => {
      if (e.key === 'Escape') onCancel()
    }
    document.addEventListener('keydown', handleEscape)
    return () => {
      clearTimeout(timer)
      document.removeEventListener('keydown', handleEscape)
    }
  }, [open, onCancel])

  useEffect(() => {
    if (!open) return
    const previouslyFocused = document.activeElement
    return () => {
      if (previouslyFocused && typeof previouslyFocused.focus === 'function') {
        previouslyFocused.focus()
      }
    }
  }, [open])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="fixed inset-0 bg-black/40" onClick={onCancel} aria-hidden="true" />
      <div
        ref={dialogRef}
        className="relative bg-white rounded-xl shadow-xl max-w-md w-full p-6 space-y-4"
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-title"
      >
        <h2 id="confirm-title" className="text-lg font-semibold text-gray-900">
          {title}
        </h2>
        <p className="text-gray-600">{message}</p>
        <div className="flex justify-end gap-3 pt-2">
          <Button variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
          <Button
            variant={variant === 'danger' ? 'primary' : 'secondary'}
            className={variant === 'danger' ? 'bg-red-600 hover:bg-red-700 text-white' : ''}
            onClick={onConfirm}
          >
            {confirmLabel || 'Confirm'}
          </Button>
        </div>
      </div>
    </div>
  )
}

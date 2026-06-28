import { useState } from 'react'
import Button from './Button'
import { paymentsService } from '../services/payments'
import { useToast } from './Toast'

export default function RecordPaymentDialog({ open, occupant, onClose, onRecorded }) {
  const { addToast } = useToast()
  const [amount, setAmount] = useState('')
  const [paymentDate, setPaymentDate] = useState(new Date().toISOString().split('T')[0])
  const [paymentMethod, setPaymentMethod] = useState('cash')
  const [reference, setReference] = useState('')
  const [notes, setNotes] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)
  const [fieldErrors, setFieldErrors] = useState({})

  if (!open) return null

  const validate = () => {
    const errs = {}
    if (!amount || Number(amount) <= 0) errs.amount = 'Enter a valid amount greater than 0.'
    if (!paymentDate) errs.date = 'Select a payment date.'
    if (reference && reference.length > 100) errs.reference = 'Reference is too long (max 100 characters).'
    setFieldErrors(errs)
    return Object.keys(errs).length === 0
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!validate()) return
    setSubmitting(true)
    setError(null)
    try {
      await paymentsService.create({
        student: occupant.id,
        amount,
        payment_date: paymentDate,
        payment_method: paymentMethod,
        reference: reference || undefined,
        notes: notes || undefined,
      })
      addToast('Payment recorded successfully.', { type: 'success' })
      onRecorded()
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  const handleClose = () => {
    setAmount('')
    setPaymentDate(new Date().toISOString().split('T')[0])
    setPaymentMethod('cash')
    setReference('')
    setNotes('')
    setError(null)
    setFieldErrors({})
    onClose()
  }

  const inputClass = (hasError) =>
    `w-full border rounded-lg px-4 py-3 text-sm focus:outline-none focus:ring-2 transition-colors ${
      hasError
        ? 'border-red-300 focus:ring-red-500 focus:border-red-500'
        : 'border-gray-300 focus:ring-primary-500 focus:border-primary-500'
    }`

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="fixed inset-0 bg-black/40" onClick={handleClose} aria-hidden="true" />
      <div
        className="relative bg-white rounded-xl shadow-xl max-w-lg w-full p-6 space-y-5"
        role="dialog"
        aria-modal="true"
        aria-labelledby="record-payment-title"
      >
        <div className="flex items-center justify-between">
          <h2 id="record-payment-title" className="text-lg font-semibold text-gray-900">
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

        <p className="text-sm text-gray-600">
          Recording payment for <span className="font-medium text-gray-900">{occupant?.full_name}</span>.
        </p>

        <form onSubmit={handleSubmit} className="space-y-4" noValidate>
          <div>
            <label htmlFor="pmt-amount" className="block text-sm font-medium text-gray-700 mb-1">
              Amount (UGX) <span className="text-red-500">*</span>
            </label>
            <input
              id="pmt-amount"
              type="number"
              step="0.01"
              min="0.01"
              required
              value={amount}
              onChange={(e) => { setAmount(e.target.value); setFieldErrors((p) => ({ ...p, amount: '' })) }}
              placeholder="e.g. 150000"
              className={inputClass(!!fieldErrors.amount)}
              aria-invalid={!!fieldErrors.amount}
              aria-describedby={fieldErrors.amount ? 'pmt-amount-error' : undefined}
            />
            {fieldErrors.amount && (
              <p id="pmt-amount-error" className="mt-1 text-sm text-red-600">{fieldErrors.amount}</p>
            )}
          </div>

          <div>
            <label htmlFor="pmt-date" className="block text-sm font-medium text-gray-700 mb-1">
              Payment Date <span className="text-red-500">*</span>
            </label>
            <input
              id="pmt-date"
              type="date"
              required
              value={paymentDate}
              onChange={(e) => setPaymentDate(e.target.value)}
              className={inputClass(!!fieldErrors.date)}
              aria-invalid={!!fieldErrors.date}
            />
            {fieldErrors.date && (
              <p className="mt-1 text-sm text-red-600">{fieldErrors.date}</p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Payment Method <span className="text-red-500">*</span>
            </label>
            <div className="grid grid-cols-3 gap-3">
              {[
                { value: 'cash', label: 'Cash' },
                { value: 'transfer', label: 'Bank Transfer' },
                { value: 'card', label: 'Card' },
              ].map((m) => (
                <button
                  key={m.value}
                  type="button"
                  onClick={() => setPaymentMethod(m.value)}
                  className={`px-4 py-3 rounded-lg border text-sm font-medium transition-colors ${
                    paymentMethod === m.value
                      ? 'border-primary-500 bg-primary-50 text-primary-700'
                      : 'border-gray-200 text-gray-700 hover:border-gray-300 hover:bg-gray-50'
                  }`}
                  aria-pressed={paymentMethod === m.value}
                >
                  {m.label}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label htmlFor="pmt-ref" className="block text-sm font-medium text-gray-700 mb-1">
              Reference <span className="text-gray-400 font-normal">(optional)</span>
            </label>
            <input
              id="pmt-ref"
              type="text"
              value={reference}
              onChange={(e) => setReference(e.target.value)}
              placeholder="e.g. Transaction ID"
              className={inputClass(!!fieldErrors.reference)}
              aria-invalid={!!fieldErrors.reference}
            />
            {fieldErrors.reference && (
              <p className="mt-1 text-sm text-red-600">{fieldErrors.reference}</p>
            )}
          </div>

          <div>
            <label htmlFor="pmt-notes" className="block text-sm font-medium text-gray-700 mb-1">
              Notes <span className="text-gray-400 font-normal">(optional)</span>
            </label>
            <textarea
              id="pmt-notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="e.g. First installment"
              rows={2}
              className={inputClass(false)}
            />
          </div>

          {error && (
            <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
              {error}
            </p>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <Button variant="secondary" type="button" onClick={handleClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={submitting}>
              {submitting ? 'Recording...' : 'Record Payment'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}

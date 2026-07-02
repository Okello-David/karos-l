import { useState } from 'react'
import Button from './Button'
import { paymentsService } from '../services/payments'
import { formatUGX } from '../utils/format'

export default function PaymentDetailDialog({ open, payment, onClose }) {
  const [pdfError, setPdfError] = useState(null)

  if (!open || !payment) return null

  const methodLabels = {
    cash: 'Cash',
    transfer: 'Bank Transfer',
    card: 'Card',
  }

  const handleReceiptPdf = async () => {
    setPdfError(null)
    try {
      const blob = await paymentsService.receiptPdf(payment.receipt_id)
      const url = URL.createObjectURL(blob)
      window.open(url, '_blank', 'noopener,noreferrer')
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (err) {
      setPdfError(err.message)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="fixed inset-0 bg-black/40" onClick={onClose} aria-hidden="true" />
      <div
        className="relative bg-white rounded-xl shadow-xl max-w-md w-full p-6 space-y-5"
        role="dialog"
        aria-modal="true"
        aria-labelledby="payment-detail-title"
      >
        <div className="flex items-center justify-between">
          <h2 id="payment-detail-title" className="text-lg font-semibold text-gray-900">
            Payment Details
          </h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-xl leading-none"
            aria-label="Close"
          >
            &times;
          </button>
        </div>

        <div className="bg-primary-50 rounded-xl px-5 py-6 text-center">
          <p className="text-sm text-gray-500 mb-1">Amount</p>
          <p className="text-3xl font-bold text-primary-700">
            {formatUGX(payment.amount)}
          </p>
        </div>

        <dl className="space-y-3 text-sm">
          <div className="flex justify-between">
            <dt className="text-gray-500">Occupant</dt>
            <dd className="font-medium text-gray-900">{payment.student_name}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-gray-500">Date</dt>
            <dd className="font-medium text-gray-900">
              {new Date(payment.payment_date).toLocaleDateString()}
            </dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-gray-500">Method</dt>
            <dd className="font-medium text-gray-900">
              {methodLabels[payment.payment_method] || payment.payment_method}
            </dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-gray-500">Reference</dt>
            <dd className="font-medium text-gray-900">
              {payment.reference || <span className="text-gray-400">&mdash;</span>}
            </dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-gray-500">Receipt</dt>
            <dd className="font-medium text-gray-900">
              {payment.receipt_number ? (
                <button
                  type="button"
                  onClick={handleReceiptPdf}
                  className="text-primary-600 hover:text-primary-700 font-mono text-xs"
                >
                  {payment.receipt_number}
                </button>
              ) : (
                <span className="text-gray-400">&mdash;</span>
              )}
            </dd>
          </div>
          <div className="flex justify-between items-start">
            <dt className="text-gray-500">Notes</dt>
            <dd className="font-medium text-gray-900 text-right max-w-[60%]">
              {payment.notes || <span className="text-gray-400">&mdash;</span>}
            </dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-gray-500">Recorded</dt>
            <dd className="font-medium text-gray-900">
              {new Date(payment.created_at).toLocaleString()}
            </dd>
          </div>
        </dl>

        {pdfError && <p className="text-sm text-red-600">{pdfError}</p>}

        <div className="flex justify-end pt-2">
          <Button variant="secondary" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>
    </div>
  )
}

import Card from '../Card'
import { Skeleton } from '../Skeleton'
import { formatUGX } from '../../utils/format'

export default function PaymentTable({ title, payments, loading = false }) {
  if (loading) {
    return (
      <Card title={title}>
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-10" />
          ))}
        </div>
      </Card>
    )
  }

  if (!payments || payments.length === 0) {
    return (
      <Card title={title}>
        <p className="text-sm text-gray-400 text-center py-8">No payments recorded yet</p>
      </Card>
    )
  }

  return (
    <Card title={title}>
      <div className="overflow-x-auto -mx-6">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200">
              <th className="text-left py-3 px-6 font-medium text-gray-500">Occupant</th>
              <th className="text-left py-3 px-6 font-medium text-gray-500">Amount</th>
              <th className="text-left py-3 px-6 font-medium text-gray-500">Date</th>
              <th className="text-left py-3 px-6 font-medium text-gray-500">Property</th>
            </tr>
          </thead>
          <tbody>
            {payments.map((p) => (
              <tr key={p.id} className="border-b border-gray-100 last:border-0 hover:bg-gray-50 transition-colors">
                <td className="py-3 px-6 text-gray-900 font-medium">{p.occupant}</td>
                <td className="py-3 px-6 text-gray-900">{formatUGX(p.amount)}</td>
                <td className="py-3 px-6 text-gray-500">{p.date}</td>
                <td className="py-3 px-6 text-gray-500">{p.property}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  )
}

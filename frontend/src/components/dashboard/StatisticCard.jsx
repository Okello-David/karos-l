import Card from '../Card'

export default function StatisticCard({ title, value, subtitle, secondary, action, className = '' }) {
  return (
    <Card className={`flex flex-col ${className}`}>
      <p className="text-sm font-medium text-gray-500 mb-3">{title}</p>
      <div className="flex items-baseline gap-1 mb-1">
        <span className="text-3xl font-bold text-gray-900">{value}</span>
        {subtitle && <span className="text-lg text-gray-400">{subtitle}</span>}
      </div>
      {secondary && (
        <p className="text-sm text-gray-500 mb-4">
          <span className="font-medium text-gray-700">{secondary.value}</span>
          {' '}{secondary.label}
        </p>
      )}
      {action && <div className="mt-auto pt-2">{action}</div>}
    </Card>
  )
}

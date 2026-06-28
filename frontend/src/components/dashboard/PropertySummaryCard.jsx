import Card from '../Card'

export default function PropertySummaryCard({ name, occupied, total, occupancyRate }) {
  const rateColor =
    occupancyRate >= 90
      ? 'text-emerald-600'
      : occupancyRate >= 70
        ? 'text-amber-600'
        : 'text-gray-600'

  return (
    <Card>
      <h3 className="text-lg font-semibold text-gray-900 mb-4">{name}</h3>
      <div className="space-y-3">
        <div className="flex items-center justify-between text-sm">
          <span className="text-gray-500">Spaces filled</span>
          <span className="font-medium text-gray-900">{occupied}/{total}</span>
        </div>
        <div className="w-full bg-gray-100 rounded-full h-2.5" role="progressbar" aria-valuenow={occupancyRate} aria-valuemin={0} aria-valuemax={100} aria-label={`${occupancyRate}% occupancy`}>
          <div
            className="bg-primary-500 rounded-full h-2.5 transition-all"
            style={{ width: `${occupancyRate}%` }}
          />
        </div>
        <div className="flex items-center justify-between text-sm">
          <span className="text-gray-500">Occupancy</span>
          <span className={`font-semibold ${rateColor}`}>{occupancyRate}%</span>
        </div>
      </div>
    </Card>
  )
}

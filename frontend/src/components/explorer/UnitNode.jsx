function getStatusColor(occupancyPercentage, isFull) {
  if (isFull || occupancyPercentage >= 100) return 'red'
  if (occupancyPercentage >= 75) return 'yellow'
  return 'green'
}

const statusConfig = {
  green: {
    badge: 'bg-green-100 text-green-700',
    bar: 'bg-green-500',
    dot: 'bg-green-500',
    label: 'Available',
  },
  yellow: {
    badge: 'bg-yellow-100 text-yellow-700',
    bar: 'bg-yellow-500',
    dot: 'bg-yellow-500',
    label: 'Nearly Full',
  },
  red: {
    badge: 'bg-red-100 text-red-700',
    bar: 'bg-red-500',
    dot: 'bg-red-500',
    label: 'Full',
  },
}

export default function UnitNode({ unit, onSelect }) {
  const status = getStatusColor(unit.occupancy_percentage, unit.is_full)
  const config = statusConfig[status]

  return (
    <button
      onClick={() => onSelect?.(unit.id)}
      className="block w-full text-left bg-white rounded-lg border border-gray-200 p-4 hover:border-gray-300 hover:shadow-sm transition-all"
    >
      <div className="flex items-center justify-between mb-3">
        <h4 className="font-medium text-gray-900 text-sm">{unit.name}</h4>
        <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${config.badge}`}>
          {config.label}
        </span>
      </div>

      <div className="space-y-2">
        <div className="flex justify-between text-xs text-gray-500">
          <span>Capacity</span>
          <span className="font-medium text-gray-700">{unit.capacity}</span>
        </div>
        <div className="flex justify-between text-xs text-gray-500">
          <span>Occupied</span>
          <span className="font-medium text-gray-700">{unit.current_occupant_count}</span>
        </div>
        <div className="flex justify-between text-xs text-gray-500">
          <span>Available</span>
          <span className="font-medium text-gray-700">{unit.available_spaces}</span>
        </div>
      </div>

      <div className="mt-3 h-1.5 bg-gray-100 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${config.bar}`}
          style={{ width: `${Math.min(unit.occupancy_percentage, 100)}%` }}
        />
      </div>

      <div className="mt-1 text-right text-xs text-gray-400">
        {unit.occupancy_percentage}% occupied
      </div>
    </button>
  )
}

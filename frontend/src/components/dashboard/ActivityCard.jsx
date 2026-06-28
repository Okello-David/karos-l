import Card from '../Card'

const typeColors = {
  checkin: 'bg-emerald-400',
  checkout: 'bg-amber-400',
  payment: 'bg-blue-400',
}

export default function ActivityCard({ title, activities }) {
  return (
    <Card title={title}>
      <div className="space-y-0">
        {activities.map((activity, i) => (
          <div key={activity.id} className="flex gap-4 py-3 border-b border-gray-100 last:border-0">
            <div className="flex flex-col items-center">
              <div className={`w-2.5 h-2.5 rounded-full mt-1.5 ${typeColors[activity.type] || 'bg-gray-300'}`} />
              {i < activities.length - 1 && <div className="w-px flex-1 bg-gray-100 mt-1" />}
            </div>
            <div className="flex-1 min-w-0 pb-1">
              <p className="text-sm text-gray-900 leading-relaxed">
                <span className="font-semibold">{activity.actor}</span>
                {' '}{activity.detail}{' '}
                <span className="font-semibold">{activity.target}</span>
              </p>
              <p className="text-xs text-gray-400 mt-0.5">{activity.time}</p>
            </div>
          </div>
        ))}
      </div>
    </Card>
  )
}

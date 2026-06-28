import Card from '../Card'

export default function ActionCard({ title, actions }) {
  return (
    <Card title={title}>
      <div className="space-y-3" data-tour="actions">
        {actions.map((action, i) => (
          <button
            key={i}
            onClick={action.onClick}
            className="w-full text-left px-4 py-3 rounded-lg border border-gray-200 text-sm font-medium text-gray-700 hover:bg-gray-50 hover:border-gray-300 transition-colors"
          >
            {action.label}
          </button>
        ))}
      </div>
    </Card>
  )
}

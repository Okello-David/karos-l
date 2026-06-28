import PageContainer from '../components/PageContainer'
import Card from '../components/Card'
import Button from '../components/Button'

const reportCards = [
  {
    title: 'Occupancy Reports',
    description: 'View occupancy rates, trends, and utilization across all properties.',
    icon: (
      <svg className="w-8 h-8 text-primary-500" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75ZM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625ZM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125Z" />
      </svg>
    ),
  },
  {
    title: 'Financial Reports',
    description: 'View payment collections, outstanding balances, and revenue summaries.',
    icon: (
      <svg className="w-8 h-8 text-emerald-500" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v12m-3-2.818.879.659c1.171.879 3.07.879 4.242 0 1.172-.879 1.172-2.303 0-3.182C13.536 12.219 12.768 12 12 12c-.725 0-1.45-.22-2.003-.659-1.106-.879-1.106-2.303 0-3.182s2.9-.879 4.006 0l.415.33M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
  },
  {
    title: 'Student Reports',
    description: 'Detailed occupant lists, contact information, and unit assignments.',
    icon: (
      <svg className="w-8 h-8 text-blue-500" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" d="M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z" />
      </svg>
    ),
  },
]

export default function Reports() {
  return (
    <PageContainer
      title="Reports & Analytics"
      description="Generate and view reports on occupancy, finances, and students."
    >
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {reportCards.map((report) => (
          <div key={report.title} className="bg-white rounded-xl border border-gray-200 p-6 hover:border-primary-300 hover:shadow-sm transition-all">
            <div className="mb-4">{report.icon}</div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">{report.title}</h3>
            <p className="text-sm text-gray-600 mb-6">{report.description}</p>
            <Button variant="secondary" disabled>
              Coming Soon
            </Button>
          </div>
        ))}
      </div>

      <div className="bg-primary-50 border border-primary-200 rounded-xl p-6 text-center">
        <p className="text-sm text-primary-800 font-medium">
          Advanced reporting features are under development. In the meantime, use the Backup & Export page to export data as CSV or Excel.
        </p>
        <div className="mt-4">
          <Button variant="secondary" onClick={() => window.location.href = '/backup'}>
            Go to Export
          </Button>
        </div>
      </div>
    </PageContainer>
  )
}

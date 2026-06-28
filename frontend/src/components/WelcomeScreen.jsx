import { useState } from 'react'
import Button from './Button'

const WELCOME_KEY = 'karos_welcome_dismissed'

function StepIndicator({ current, total }) {
  return (
    <div className="flex justify-center gap-2" aria-hidden="true">
      {Array.from({ length: total }).map((_, i) => (
        <div
          key={i}
          className={`h-2 rounded-full transition-all duration-300 ${
            i === current ? 'w-8 bg-primary-600' : 'w-2 bg-gray-300'
          }`}
        />
      ))}
    </div>
  )
}

const steps = [
  {
    title: 'Welcome to KarosL',
    description: 'Your property management platform. Manage occupants, track payments, explore properties, and more — all in one place.',
    icon: (
      <svg className="w-16 h-16 text-primary-600" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z" />
      </svg>
    ),
  },
  {
    title: 'Manage Occupants & Payments',
    description: 'Register students, assign them to units, record payments, and automatically generate receipts. View outstanding balances at a glance.',
    icon: (
      <svg className="w-16 h-16 text-green-500" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" d="M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z" />
      </svg>
    ),
  },
  {
    title: 'Explore & Monitor',
    description: 'Use the Property Explorer to visualize occupancy across all properties, sections, and units. Track income and generate reports.',
    icon: (
      <svg className="w-16 h-16 text-blue-500" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 6.75V15m6-6v8.25m.503 3.498l4.875-2.437c.381-.19.622-.58.622-1.006V4.82c0-.836-.88-1.38-1.628-1.006l-3.869 1.934c-.317.159-.69.159-1.006 0L9.503 3.252a1.125 1.125 0 00-1.006 0L3.622 5.689C3.24 5.88 3 6.27 3 6.695V19.18c0 .836.88 1.38 1.628 1.006l3.869-1.934c.317-.159.69-.159 1.006 0l4.994 2.497c.317.158.69.158 1.006 0z" />
      </svg>
    ),
  },
  {
    title: 'Keyboard Shortcuts',
    description: 'Press Ctrl+K to search globally, press ? to view all available keyboard shortcuts. Navigate faster with hotkeys.',
    icon: (
      <svg className="w-16 h-16 text-purple-500" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.325.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.241-.438.613-.43.992a7.723 7.723 0 010 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.955.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.47 6.47 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.281c-.09.543-.56.94-1.11.94h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.991a6.932 6.932 0 010-.255c.007-.38-.138-.751-.43-.992l-1.004-.827a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.086.22-.128.332-.183.582-.495.644-.869l.214-1.28z" />
        <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
    ),
  },
]

export default function WelcomeScreen({ onDismiss }) {
  const [step, setStep] = useState(0)
  const isLast = step === steps.length - 1

  const handleDismiss = () => {
    localStorage.setItem(WELCOME_KEY, 'true')
    onDismiss?.()
  }

  return (
    <div
      className="fixed inset-0 z-[95] flex items-center justify-center p-4 bg-black/40"
      onClick={handleDismiss}
      role="dialog"
      aria-modal="true"
      aria-label="Welcome to KarosL"
    >
      <div
        className="bg-white rounded-2xl shadow-2xl max-w-lg w-full p-8 text-center"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-6 flex justify-center">
          {steps[step].icon}
        </div>

        <h2 className="text-2xl font-bold text-gray-900 mb-3">
          {steps[step].title}
        </h2>
        <p className="text-gray-600 leading-relaxed mb-8">
          {steps[step].description}
        </p>

        <div className="mb-8">
          <StepIndicator current={step} total={steps.length} />
        </div>

        <div className="flex items-center justify-center gap-3">
          {!isLast && (
            <Button variant="ghost" size="sm" onClick={handleDismiss}>
              Skip tour
            </Button>
          )}
          {isLast ? (
            <Button onClick={handleDismiss}>
              Get Started
            </Button>
          ) : (
            <Button onClick={() => setStep((s) => s + 1)}>
              Next
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}

export function isWelcomeDismissed() {
  return localStorage.getItem(WELCOME_KEY) === 'true'
}

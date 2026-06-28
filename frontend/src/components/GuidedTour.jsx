import { useState, useEffect, useCallback } from 'react'
import Button from './Button'

const TOUR_KEY = 'karos_tour_dismissed'

const defaultSteps = [
  {
    target: '#main-content',
    title: 'Welcome to the Dashboard',
    description: 'This is your command center. View occupancy stats, recent payments, and quick actions at a glance.',
    position: 'center',
  },
  {
    target: '[data-tour="sidebar"]',
    title: 'Sidebar Navigation',
    description: 'Use the sidebar to navigate between pages. Each section gives you access to different features.',
    position: 'right',
  },
  {
    target: '[data-tour="topbar-search"]',
    title: 'Global Search',
    description: 'Press Ctrl+K to search across occupants, receipts, and properties from anywhere in the app.',
    position: 'bottom',
  },
  {
    target: '[data-tour="explorer-link"]',
    title: 'Property Explorer',
    description: 'Visualize your property layout, check occupancy rates, and drill down into sections and units.',
    position: 'right',
  },
  {
    target: '[data-tour="actions"]',
    title: 'Quick Actions',
    description: 'Common tasks like registering occupants and recording payments are always one click away.',
    position: 'top',
  },
]

function getTargetRect(selector) {
  const el = document.querySelector(selector)
  if (!el) return null
  return el.getBoundingClientRect()
}

function TooltipContent({ step, current, total, onPrev, onNext, onSkip, position }) {
  const positions = {
    bottom: 'top-full left-1/2 -translate-x-1/2 mt-3',
    top: 'bottom-full left-1/2 -translate-x-1/2 mb-3',
    left: 'right-full top-1/2 -translate-y-1/2 mr-3',
    right: 'left-full top-1/2 -translate-y-1/2 ml-3',
    center: '',
  }

  const arrows = {
    bottom: 'bottom-full left-1/2 -translate-x-1/2 border-8 border-transparent border-b-white',
    top: 'top-full left-1/2 -translate-x-1/2 border-8 border-transparent border-t-white',
    left: 'left-full top-1/2 -translate-y-1/2 border-8 border-transparent border-l-white',
    right: 'right-full top-1/2 -translate-y-1/2 border-8 border-transparent border-r-white',
  }

  if (position === 'center') {
    return (
      <div className="bg-white rounded-xl shadow-2xl max-w-sm w-full p-6">
        <p className="text-xs font-semibold text-primary-600 uppercase tracking-wider mb-2">
          Step {current + 1} of {total}
        </p>
        <h3 className="text-lg font-semibold text-gray-900 mb-2">{step.title}</h3>
        <p className="text-sm text-gray-600 mb-6">{step.description}</p>
        <div className="flex items-center justify-between">
          <Button variant="ghost" size="sm" onClick={onSkip}>Skip tour</Button>
          <div className="flex gap-2">
            {current > 0 && (
              <Button variant="secondary" size="sm" onClick={onPrev}>Back</Button>
            )}
            <Button size="sm" onClick={onNext}>
              {current === total - 1 ? 'Finish' : 'Next'}
            </Button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className={`absolute z-10 ${positions[position] || 'bottom'}`}>
      <div className={`absolute ${arrows[position] || 'bottom-full'}`} />
      <div className="bg-white rounded-xl shadow-2xl max-w-xs w-full p-4">
        <p className="text-xs font-semibold text-primary-600 uppercase tracking-wider mb-1">
          {current + 1} / {total}
        </p>
        <h3 className="text-sm font-semibold text-gray-900 mb-1">{step.title}</h3>
        <p className="text-xs text-gray-600 mb-4">{step.description}</p>
        <div className="flex items-center justify-between">
          <button onClick={onSkip} className="text-xs text-gray-400 hover:text-gray-600">Skip</button>
          <div className="flex gap-2">
            {current > 0 && (
              <button onClick={onPrev} className="text-xs text-gray-500 hover:text-gray-700">Back</button>
            )}
            <button
              onClick={onNext}
              className="text-xs font-medium text-white bg-primary-600 px-3 py-1.5 rounded-lg hover:bg-primary-700"
            >
              {current === total - 1 ? 'Finish' : 'Next'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default function GuidedTour({ open, onClose, steps = defaultSteps }) {
  const [current, setCurrent] = useState(0)
  const [targetRect, setTargetRect] = useState(null)

  const updateRect = useCallback(() => {
    if (!steps[current]) return
    if (steps[current].position === 'center') {
      setTargetRect(null)
      return
    }
    const rect = getTargetRect(steps[current].target)
    setTargetRect(rect)
  }, [current, steps])

  useEffect(() => {
    if (!open) return
    updateRect()
    window.addEventListener('resize', updateRect)
    const observer = new MutationObserver(updateRect)
    observer.observe(document.body, { childList: true, subtree: true })
    return () => {
      window.removeEventListener('resize', updateRect)
      observer.disconnect()
    }
  }, [open, updateRect])

  useEffect(() => {
    if (!open) return
    function handler(e) {
      if (e.key === 'Escape') handleClose()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [open, current])

  const handleClose = () => {
    localStorage.setItem(TOUR_KEY, 'true')
    onClose?.()
  }

  const handleNext = () => {
    if (current === steps.length - 1) {
      handleClose()
    } else {
      setCurrent((c) => c + 1)
    }
  }

  const handlePrev = () => {
    setCurrent((c) => Math.max(0, c - 1))
  }

  if (!open) return null

  const step = steps[current]

  return (
    <>
      <div className="fixed inset-0 z-[85]" onClick={handleClose} />
      {targetRect && (
        <div
          className="fixed z-[86] rounded-xl ring-2 ring-primary-400 ring-offset-2 transition-all duration-300"
          style={{
            top: targetRect.top - 4,
            left: targetRect.left - 4,
            width: targetRect.width + 8,
            height: targetRect.height + 8,
          }}
        />
      )}
      <div className="fixed z-[87]" style={targetRect ? { top: 0, left: 0 } : {
        top: '50%', left: '50%', transform: 'translate(-50%, -50%)',
      }}>
        <TooltipContent
          step={step}
          current={current}
          total={steps.length}
          onPrev={handlePrev}
          onNext={handleNext}
          onSkip={handleClose}
          position={step.position}
        />
      </div>
    </>
  )
}

export function isTourDismissed() {
  return localStorage.getItem(TOUR_KEY) === 'true'
}

export function resetTour() {
  localStorage.removeItem(TOUR_KEY)
  localStorage.removeItem('karos_welcome_dismissed')
}

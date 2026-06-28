import { useState, useCallback } from 'react'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import Sidebar from '../components/Sidebar'
import Topbar from '../components/Topbar'
import { ToastProvider } from '../components/Toast'
import WelcomeScreen, { isWelcomeDismissed } from '../components/WelcomeScreen'
import GuidedTour, { isTourDismissed } from '../components/GuidedTour'
import GlobalSearch from '../components/GlobalSearch'
import KeyboardShortcutsHelp from '../components/KeyboardShortcutsHelp'
import { useKeyboardShortcuts } from '../hooks/useKeyboardShortcuts'

const pageTitles = {
  '/': 'Overview',
  '/explorer': 'Property Explorer',
  '/properties': 'Properties',
  '/occupants': 'Occupants',
  '/payments': 'Payments',
  '/receipts': 'Receipts',
  '/backup': 'Backup',
  '/reports': 'Reports',
  '/administration': 'Administration',
}

export default function MainLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const location = useLocation()
  const navigate = useNavigate()
  const title = pageTitles[location.pathname] || 'Page'

  const [showWelcome, setShowWelcome] = useState(() => !isWelcomeDismissed())
  const [showTour, setShowTour] = useState(false)
  const [showSearch, setShowSearch] = useState(false)
  const [showShortcuts, setShowShortcuts] = useState(false)

  const handleWelcomeDismiss = useCallback(() => {
    setShowWelcome(false)
    if (!isTourDismissed()) {
      setShowTour(true)
    }
  }, [])

  const shortcuts = [
    { key: 'k', ctrl: true, action: () => setShowSearch(true) },
    { key: '?', action: () => setShowShortcuts(true) },
    { key: 'Escape', action: () => {} },
    { key: 'h', action: () => navigate('/') },
    { key: 'e', action: () => navigate('/explorer') },
    { key: 'o', action: () => navigate('/occupants') },
    { key: 'p', action: () => navigate('/payments') },
    { key: 'r', action: () => navigate('/receipts') },
    { key: '/', action: () => {
      const input = document.querySelector('input[type="text"]')
      if (input) input.focus()
    }},
  ]

  useKeyboardShortcuts(shortcuts)

  return (
    <ToastProvider>
      <div className="min-h-screen bg-gray-50">
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-[100] focus:px-4 focus:py-2 focus:bg-primary-600 focus:text-white focus:rounded-lg focus:shadow-lg"
        >
          Skip to main content
        </a>

        <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

        <div className="lg:pl-64 flex flex-col min-h-screen">
          <Topbar
            title={title}
            pathname={location.pathname}
            onMenuClick={() => setSidebarOpen(true)}
          />
          <main id="main-content" className="flex-1" tabIndex={-1}>
            <Outlet />
          </main>
        </div>

        {showWelcome && (
          <WelcomeScreen onDismiss={handleWelcomeDismiss} />
        )}

        {showTour && (
          <GuidedTour
            open={showTour}
            onClose={() => setShowTour(false)}
          />
        )}

        <GlobalSearch
          open={showSearch}
          onClose={() => setShowSearch(false)}
        />

        <KeyboardShortcutsHelp
          open={showShortcuts}
          onClose={() => setShowShortcuts(false)}
        />
      </div>
    </ToastProvider>
  )
}

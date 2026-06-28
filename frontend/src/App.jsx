import { BrowserRouter, Routes, Route } from 'react-router-dom'
import MainLayout from './layouts/MainLayout'
import Dashboard from './pages/Dashboard'
import Explorer from './pages/Explorer'
import Properties from './pages/Properties'
import Occupants from './pages/Occupants'
import OccupantDetail from './pages/OccupantDetail'
import OccupantForm from './pages/OccupantForm'
import Payments from './pages/Payments'
import Receipts from './pages/Receipts'
import Reports from './pages/Reports'
import Backup from './pages/Backup'
import Administration from './pages/Administration'
import NotFound from './pages/NotFound'

import ErrorBoundary from './components/ErrorBoundary'

export default function App() {
  return (
    <BrowserRouter>
      <ErrorBoundary>
        <Routes>
          <Route element={<MainLayout />}>
            <Route index element={<Dashboard />} />
            <Route path="explorer" element={<Explorer />} />
            <Route path="properties" element={<Properties />} />
            <Route path="occupants" element={<Occupants />} />
            <Route path="occupants/new" element={<OccupantForm />} />
            <Route path="occupants/:id" element={<OccupantDetail />} />
            <Route path="occupants/:id/edit" element={<OccupantForm />} />
            <Route path="payments" element={<Payments />} />
            <Route path="receipts" element={<Receipts />} />
            <Route path="reports" element={<Reports />} />
            <Route path="backup" element={<Backup />} />
            <Route path="administration" element={<Administration />} />
            <Route path="*" element={<NotFound />} />
          </Route>
        </Routes>
      </ErrorBoundary>
    </BrowserRouter>
  )
}

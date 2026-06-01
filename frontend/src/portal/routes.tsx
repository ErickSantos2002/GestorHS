import { Routes, Route } from 'react-router-dom'
import { PlaceholderPage } from './pages/PlaceholderPage'

export default function PortalRoutes() {
  return (
    <Routes>
      <Route path="*" element={<PlaceholderPage />} />
    </Routes>
  )
}

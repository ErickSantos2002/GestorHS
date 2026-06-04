import { Routes, Route, Navigate } from 'react-router-dom'
import { PortalAuthProvider } from './PortalAuthContext'
import { PortalProtectedRoute } from './PortalProtectedRoute'
import { PortalLoginPage } from './PortalLoginPage'
import { PortalLayout } from './PortalLayout'
import { PortalHomePage } from './PortalHomePage'
import { EmBrevePage } from './EmBrevePage'

export default function PortalRoutes() {
  return (
    <PortalAuthProvider>
      <Routes>
        <Route path="login" element={<PortalLoginPage />} />
        <Route
          path="*"
          element={
            <PortalProtectedRoute>
              <PortalLayout>
                <Routes>
                  <Route index element={<PortalHomePage />} />
                  <Route path="frota" element={<EmBrevePage />} />
                  <Route path="certificados" element={<EmBrevePage />} />
                  <Route path="os" element={<EmBrevePage />} />
                  <Route path="*" element={<Navigate to="/portal" replace />} />
                </Routes>
              </PortalLayout>
            </PortalProtectedRoute>
          }
        />
      </Routes>
    </PortalAuthProvider>
  )
}

import { Routes, Route, Navigate } from 'react-router-dom'
import { PortalAuthProvider } from './PortalAuthContext'
import { PortalProtectedRoute } from './PortalProtectedRoute'
import { PortalLoginPage } from './PortalLoginPage'
import { PortalLayout } from './PortalLayout'
import { PortalHomePage } from './PortalHomePage'
import { PortalFrotaPage } from './PortalFrotaPage'
import { PortalCertificadosPage } from './PortalCertificadosPage'
import { PortalOSPage } from './PortalOSPage'
import { PortalSolicitacoesPage } from './PortalSolicitacoesPage'

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
                  <Route path="frota" element={<PortalFrotaPage />} />
                  <Route path="certificados" element={<PortalCertificadosPage />} />
                  <Route path="os" element={<PortalOSPage />} />
                  <Route path="solicitacoes" element={<PortalSolicitacoesPage />} />
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

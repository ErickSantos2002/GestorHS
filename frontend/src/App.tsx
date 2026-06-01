import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './auth/AuthContext'
import { ProtectedRoute } from './auth/ProtectedRoute'
import { LoginPage } from './app/pages/LoginPage'
import { Spinner } from './components/ui/Spinner'

const AppRoutes = lazy(() => import('./app/routes'))
const PortalRoutes = lazy(() => import('./portal/routes'))

function FullScreenSpinner() {
  return (
    <div className="flex h-screen items-center justify-center bg-background">
      <Spinner className="w-8 h-8" />
    </div>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Suspense fallback={<FullScreenSpinner />}>
          <Routes>
            <Route path="/" element={<Navigate to="/app" replace />} />
            <Route path="/login" element={<LoginPage />} />
            <Route
              path="/app/*"
              element={
                <ProtectedRoute>
                  <AppRoutes />
                </ProtectedRoute>
              }
            />
            <Route path="/portal/*" element={<PortalRoutes />} />
            <Route path="*" element={<Navigate to="/app" replace />} />
          </Routes>
        </Suspense>
      </BrowserRouter>
    </AuthProvider>
  )
}

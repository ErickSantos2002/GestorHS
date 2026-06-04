import { type ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { usePortalAuth } from './PortalAuthContext'
import { Spinner } from '../components/ui/Spinner'

export function PortalProtectedRoute({ children }: { children: ReactNode }) {
  const { cliente, loading } = usePortalAuth()
  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <Spinner className="w-8 h-8" />
      </div>
    )
  }
  if (!cliente) return <Navigate to="/portal/login" replace />
  return <>{children}</>
}

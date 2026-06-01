import { Routes, Route, Navigate } from 'react-router-dom'
import { MainLayout } from '../layout/MainLayout'
import { DashboardPage } from './pages/DashboardPage'

export default function AppRoutes() {
  return (
    <MainLayout>
      <Routes>
        <Route index element={<DashboardPage />} />
        <Route path="*" element={<Navigate to="/app" replace />} />
      </Routes>
    </MainLayout>
  )
}

import { Routes, Route, Navigate } from 'react-router-dom'
import { MainLayout } from '../layout/MainLayout'
import { DashboardPage } from './pages/DashboardPage'
import { MinhaContaPage } from './pages/MinhaContaPage'
import { UsuariosPage } from './acesso/UsuariosPage'

export default function AppRoutes() {
  return (
    <MainLayout>
      <Routes>
        <Route index element={<DashboardPage />} />
        <Route path="usuarios" element={<UsuariosPage />} />
        <Route path="conta" element={<MinhaContaPage />} />
        <Route path="*" element={<Navigate to="/app" replace />} />
      </Routes>
    </MainLayout>
  )
}

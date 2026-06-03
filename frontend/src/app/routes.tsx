import { Routes, Route, Navigate } from 'react-router-dom'
import { MainLayout } from '../layout/MainLayout'
import { DashboardPage } from './pages/DashboardPage'
import { MinhaContaPage } from './pages/MinhaContaPage'
import { UsuariosPage } from './acesso/UsuariosPage'
import { CadastrosPage } from './cadastros/CadastrosPage'
import { ClientesPage } from './clientes/ClientesPage'
import { ClienteDetailPage } from './clientes/ClienteDetailPage'
import { FrotaPage } from './frota/FrotaPage'
import { EquipamentoClienteDetailPage } from './frota/EquipamentoClienteDetailPage'
import { OrdensPage } from './ordens/OrdensPage'

export default function AppRoutes() {
  return (
    <MainLayout>
      <Routes>
        <Route index element={<DashboardPage />} />
        <Route path="usuarios" element={<UsuariosPage />} />
        <Route path="cadastros" element={<CadastrosPage />} />
        <Route path="clientes" element={<ClientesPage />} />
        <Route path="clientes/novo" element={<ClienteDetailPage />} />
        <Route path="clientes/:id" element={<ClienteDetailPage />} />
        <Route path="frota" element={<FrotaPage />} />
        <Route path="frota/novo" element={<EquipamentoClienteDetailPage />} />
        <Route path="frota/:id" element={<EquipamentoClienteDetailPage />} />
        <Route path="ordens" element={<OrdensPage />} />
        <Route path="conta" element={<MinhaContaPage />} />
        <Route path="*" element={<Navigate to="/app" replace />} />
      </Routes>
    </MainLayout>
  )
}

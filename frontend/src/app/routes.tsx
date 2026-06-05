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
import { OrdemDetailPage } from './ordens/OrdemDetailPage'
import { CobrancaPage } from './alertas/CobrancaPage'
import { SolicitacoesPage } from './solicitacoes/SolicitacoesPage'
import { CaixasPage } from './caixas/CaixasPage'
import { CaixaDetailPage } from './caixas/CaixaDetailPage'

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
        <Route path="ordens/:id" element={<OrdemDetailPage />} />
        <Route path="caixas" element={<CaixasPage />} />
        <Route path="caixas/:id" element={<CaixaDetailPage />} />
        <Route path="cobranca" element={<CobrancaPage />} />
        <Route path="solicitacoes" element={<SolicitacoesPage />} />
        <Route path="conta" element={<MinhaContaPage />} />
        <Route path="*" element={<Navigate to="/app" replace />} />
      </Routes>
    </MainLayout>
  )
}

import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth/AuthContext";
import { Layout } from "./components/Layout";
import { AuditoriaPage } from "./pages/AuditoriaPage";
import { DashboardPage } from "./pages/DashboardPage";
import { ErrosPage } from "./pages/ErrosPage";
import { FilasPage } from "./pages/FilasPage";
import { IntegracoesPage } from "./pages/IntegracoesPage";
import { LoginLogsPage } from "./pages/LoginLogsPage";
import { LoginPage } from "./pages/LoginPage";
import { MaquininhasPage } from "./pages/MaquininhasPage";
import { MapeamentosPage } from "./pages/MapeamentosPage";
import { SchedulerPage } from "./pages/SchedulerPage";

function Private({ children }: { children: React.ReactNode }) {
  const { token } = useAuth();
  if (!token) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function AdminOnly({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  if (!user?.admin) return <Navigate to="/" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <Private>
            <Layout />
          </Private>
        }
      >
        <Route index element={<DashboardPage />} />
        <Route path="integracoes" element={<IntegracoesPage />} />
        <Route path="erros" element={<ErrosPage />} />
        <Route
          path="auditoria"
          element={
            <AdminOnly>
              <AuditoriaPage />
            </AdminOnly>
          }
        />
        <Route
          path="scheduler"
          element={
            <AdminOnly>
              <SchedulerPage />
            </AdminOnly>
          }
        />
        <Route path="cadastros/maquininhas" element={<MaquininhasPage />} />
        <Route path="cadastros/mapeamentos" element={<MapeamentosPage />} />
        <Route path="filas" element={<FilasPage />} />
        <Route
          path="acessos"
          element={
            <AdminOnly>
              <LoginLogsPage />
            </AdminOnly>
          }
        />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

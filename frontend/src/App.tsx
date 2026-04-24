import "@/App.css"
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom"
import { AuthProvider, useAuth } from "./context/AuthContext"
import { DOTokenProvider } from "./context/DOTokenContext"
import Login from "./pages/Login"
import Register from "./pages/Register"
import VerifyEmail from "./pages/VerifyEmail"
import ForgotPassword from "./pages/ForgotPassword"
import ResetPassword from "./pages/ResetPassword"
import Dashboard from "./pages/Dashboard"
import DropletDetail from "./pages/DropletDetail"
import DeployWizard from "./pages/DeployWizard"
import Settings from "./pages/Settings"
import Templates from "./pages/Templates"
import { Toaster } from "./components/ui/sonner"

function Protected({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) {
    return <div className="min-h-screen flex items-center justify-center text-neutral-500 font-mono text-sm">Checking session…</div>
  }
  if (!user) return <Navigate to="/login" replace />
  return <DOTokenProvider>{children}</DOTokenProvider>
}

function AppRouter() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/reset-password" element={<ResetPassword />} />
      <Route path="/verify-email" element={<VerifyEmail />} />
      <Route
        path="/droplets"
        element={
          <Protected>
            <Dashboard />
          </Protected>
        }
      />
      <Route
        path="/droplets/:id"
        element={
          <Protected>
            <DropletDetail />
          </Protected>
        }
      />
      <Route
        path="/deploy"
        element={
          <Protected>
            <DeployWizard />
          </Protected>
        }
      />
      <Route
        path="/settings"
        element={
          <Protected>
            <Settings />
          </Protected>
        }
      />
      <Route
        path="/templates"
        element={
          <Protected>
            <Templates />
          </Protected>
        }
      />
      <Route path="/" element={<Navigate to="/droplets" replace />} />
      <Route path="*" element={<Navigate to="/droplets" replace />} />
    </Routes>
  )
}

export default function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <AuthProvider>
          <AppRouter />
          <Toaster
            theme="dark"
            position="bottom-right"
            toastOptions={{
              style: {
                background: "#0f0f10",
                border: "1px solid rgba(255,255,255,0.1)",
                borderRadius: 0,
                fontFamily: "IBM Plex Sans, sans-serif",
              },
            }}
          />
        </AuthProvider>
      </BrowserRouter>
    </div>
  )
}

import "@/App.css";
import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
  useLocation,
} from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { DOTokenProvider } from "./context/DOTokenContext";
import Login from "./pages/Login";
import Register from "./pages/Register";
import AuthCallback from "./pages/AuthCallback";
import Dashboard from "./pages/Dashboard";
import DropletDetail from "./pages/DropletDetail";
import DeployWizard from "./pages/DeployWizard";
import Settings from "./pages/Settings";
import { Toaster } from "./components/ui/sonner";

function Protected({ children }) {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center text-neutral-500 font-mono text-sm">
        Checking session…
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  return <DOTokenProvider>{children}</DOTokenProvider>;
}

function AppRouter() {
  const location = useLocation();
  // Handle Google OAuth redirect (URL fragment #session_id=...)
  if (location.hash && location.hash.includes("session_id=")) {
    return <AuthCallback />;
  }
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/auth/callback" element={<AuthCallback />} />
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
      <Route path="/" element={<Navigate to="/droplets" replace />} />
      <Route path="*" element={<Navigate to="/droplets" replace />} />
    </Routes>
  );
}

function App() {
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
  );
}

export default App;

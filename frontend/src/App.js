import "@/App.css";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { TokenProvider, useTokenCtx } from "./context/TokenContext";
import Landing from "./pages/Landing";
import Dashboard from "./pages/Dashboard";
import DropletDetail from "./pages/DropletDetail";
import { Toaster } from "./components/ui/sonner";

function Protected({ children }) {
  const { token, account, validating } = useTokenCtx();
  if (!token) return <Navigate to="/" replace />;
  if (!account && validating) {
    return (
      <div className="min-h-screen flex items-center justify-center text-neutral-500 font-mono">
        Validating token…
      </div>
    );
  }
  if (!account && !validating) return <Navigate to="/" replace />;
  return children;
}

function AppRoutes() {
  const { token, account } = useTokenCtx();
  return (
    <Routes>
      <Route
        path="/"
        element={token && account ? <Navigate to="/droplets" replace /> : <Landing />}
      />
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
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <TokenProvider>
          <AppRoutes />
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
        </TokenProvider>
      </BrowserRouter>
    </div>
  );
}

export default App;

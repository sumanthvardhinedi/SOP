import { useEffect } from "react";
import { AuthProvider, useAuth } from "./hooks/useAuth";
import { LoginPage } from "./pages/LoginPage";
import { DashboardPage } from "./pages/DashboardPage";
import { Brand } from "./components/layout/Brand";
import { ErrorNotice, Spinner } from "./components/layout/Feedback";

function AuthenticatedApp() {
  const { user, loading, error, restore, signOut } = useAuth();
  useEffect(() => {
    if (!loading && !error) {
      window.history.replaceState(null, "", user ? "/dashboard" : "/login");
      document.title = `${user ? "Dashboard" : "Sign in"} · SalesFlow`;
    }
  }, [user, loading, error]);
  if (loading || error)
    return (
      <main className="session-screen">
        <Brand />
        {loading ? (
          <p className="session-loading">
            <Spinner />
            Opening your workspace…
          </p>
        ) : (
          <>
            <ErrorNotice error={error} />
            <button
              className="button button-primary"
              onClick={() => void restore()}
            >
              Try again
            </button>
            <button className="text-button" onClick={signOut}>
              Return to sign in
            </button>
          </>
        )}
      </main>
    );
  return user ? <DashboardPage key={user.id} /> : <LoginPage />;
}
export default function App() {
  return (
    <AuthProvider>
      <AuthenticatedApp />
    </AuthProvider>
  );
}

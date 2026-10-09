import { useEffect, useState } from "react";
import { AuthProvider, useAuth } from "./hooks/useAuth";
import { LoginPage } from "./pages/LoginPage";
import { RegisterPage } from "./pages/RegisterPage";
import { DashboardPage } from "./pages/DashboardPage";
import { Brand } from "./components/layout/Brand";
import { ErrorNotice, Spinner } from "./components/layout/Feedback";

type AuthView = "login" | "register";

function getInitialView(): AuthView {
  return window.location.pathname === "/register" ? "register" : "login";
}

function AuthenticatedApp() {
  const { user, loading, error, restore, signOut } = useAuth();
  const [view, setView] = useState<AuthView>(getInitialView);
  const [notice, setNotice] = useState("");

  useEffect(() => {
    const onPopState = () => {
      setView(window.location.pathname === "/register" ? "register" : "login");
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  useEffect(() => {
    if (user) {
      setView("login");
      setNotice("");
    }
  }, [user]);

  useEffect(() => {
    if (!loading && !error) {
      const targetPath = user
        ? "/dashboard"
        : view === "register"
          ? "/register"
          : "/login";
      const targetTitle = user
        ? "Dashboard"
        : view === "register"
          ? "Create account"
          : "Sign in";
      window.history.replaceState(null, "", targetPath);
      document.title = `${targetTitle} · SalesFlow`;
    }
  }, [user, loading, error, view]);

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

  if (user) return <DashboardPage key={user.id} />;

  return view === "register" ? (
    <RegisterPage
      onNavigateLogin={() => {
        setNotice("");
        setView("login");
        window.history.pushState(null, "", "/login");
      }}
      onRegistered={(message) => {
        setNotice(message);
        setView("login");
        window.history.pushState(null, "", "/login");
      }}
    />
  ) : (
    <LoginPage
      notice={notice}
      onNavigateRegister={() => {
        setNotice("");
        setView("register");
        window.history.pushState(null, "", "/register");
      }}
    />
  );
}
export default function App() {
  return (
    <AuthProvider>
      <AuthenticatedApp />
    </AuthProvider>
  );
}

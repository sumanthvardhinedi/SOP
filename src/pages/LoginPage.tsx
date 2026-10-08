import { useState, type FormEvent } from "react";
import { ArrowRight, LockKeyhole, Check } from "lucide-react";
import { useAuth } from "../hooks/useAuth";
import { Brand } from "../components/layout/Brand";
import { ErrorNotice, Spinner } from "../components/layout/Feedback";

export function LoginPage() {
  const { signIn } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    if (!email.trim() || !password) {
      setError("Enter your email and password.");
      return;
    }
    setPending(true);
    try {
      await signIn({ email: email.trim(), password });
    } catch (failure) {
      setError(
        failure instanceof Error
          ? failure.message
          : "Unable to sign in. Please try again.",
      );
    } finally {
      setPending(false);
    }
  }
  return (
    <main className="login-page">
      <div className="login-top">
        <Brand />
        <span className="subtle-label">YOUR SALES, IN FOCUS</span>
      </div>
      <div className="login-layout">
        <section className="login-intro">
          <span className="eyebrow">
            <span className="small-dot" /> A CLEARER VIEW OF YOUR BUSINESS
          </span>
          <p className="intro-title">
            Less spreadsheet.
            <br />
            More <span>perspective.</span>
          </p>
          <p className="intro-description">
            Your daily sales, together in one place.
            <br />A little less busywork. A lot more clarity.
          </p>
          <div className="login-benefits">
            <p>
              <Check size={16} />
              All your shop’s sales in one workspace
            </p>
            <p>
              <Check size={16} />
              Simple Excel uploads, accurate records
            </p>
            <p>
              <Check size={16} />
              The details you need, without the noise
            </p>
          </div>
          <div className="intro-footnote">
            <span className="footnote-line" />
            Built for the way your shop works.
          </div>
        </section>
        <section className="login-card card" aria-labelledby="login-title">
          <div className="login-icon">
            <LockKeyhole size={23} />
          </div>
          <h1 id="login-title">Welcome back</h1>
          <p className="muted">Sales data, simplified.</p>
          <form onSubmit={submit} className="login-form">
            <div className="field">
              <label htmlFor="email">Email address</label>
              <input
                id="email"
                type="email"
                autoComplete="username"
                placeholder="you@company.com"
                required
                maxLength={254}
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                disabled={pending}
              />
            </div>
            <div className="field">
              <label htmlFor="password">Password</label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                placeholder="Enter your password"
                required
                maxLength={128}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                disabled={pending}
              />
            </div>
            {error && <ErrorNotice error={error} />}
            <button
              className="button button-primary login-submit"
              disabled={pending}
            >
              {pending ? (
                <>
                  <Spinner />
                  Signing in…
                </>
              ) : (
                <>
                  Sign In
                  <ArrowRight size={17} />
                </>
              )}
            </button>
          </form>
          <p className="login-help">
            Use the account provided by your shop administrator.
          </p>
        </section>
      </div>
      <footer className="login-footer">
        <span>SalesFlow · Sales data, simplified.</span>
        <span>
          <LockKeyhole size={13} /> Your workspace. Your shop’s data.
        </span>
      </footer>
    </main>
  );
}

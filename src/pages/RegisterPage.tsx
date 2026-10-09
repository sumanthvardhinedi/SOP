import { useState, type FormEvent } from "react";
import { ArrowRight, Check, LockKeyhole, UserPlus } from "lucide-react";
import { api } from "../services/api";
import { Brand } from "../components/layout/Brand";
import { ErrorNotice, Spinner, SuccessNotice } from "../components/layout/Feedback";

export function RegisterPage({
  onNavigateLogin,
  onRegistered,
}: {
  onNavigateLogin?: () => void;
  onRegistered?: (message: string) => void;
}) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [shopId, setShopId] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<Error | string>("");
  const [success, setSuccess] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setSuccess("");

    const form = event.currentTarget;
    const readField = (current: string, selector: string) =>
      current || form.querySelector<HTMLInputElement>(selector)?.value || "";

    const trimmedName = readField(name, "#name").trim();
    const trimmedEmail = readField(email, "#email").trim();
    const rawPassword = readField(password, "#password");
    const trimmedShopId = readField(shopId, "#shop_id").trim();

    setName(trimmedName);
    setEmail(trimmedEmail);
    setPassword(rawPassword);
    setShopId(trimmedShopId);

    if (!trimmedName || !trimmedEmail || !rawPassword || !trimmedShopId) {
      setError("Complete all fields to create your account.");
      return;
    }

    const parsedShopId = Number(trimmedShopId);
    if (!Number.isInteger(parsedShopId) || parsedShopId <= 0) {
      setError("Shop ID must be a positive whole number.");
      return;
    }

    setPending(true);
    try {
      await api.register({
        name: trimmedName,
        email: trimmedEmail,
        password: rawPassword,
        shop_id: parsedShopId,
      });
      const message = "Account created successfully. Please sign in.";
      setSuccess(message);
      if (onRegistered) {
        onRegistered(message);
      } else {
        window.history.replaceState(null, "", "/login");
      }
    } catch (failure) {
      setError(
        failure instanceof Error
          ? failure
          : "Unable to create account. Please try again.",
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
        <section className="login-card card" aria-labelledby="register-title">
          <div className="login-icon">
            <UserPlus size={23} />
          </div>
          <h1 id="register-title">Create your account</h1>
          <p className="muted">Set up your workspace for your shop.</p>
          <form onSubmit={submit} className="login-form" noValidate>
            <div className="field">
              <label htmlFor="name">Full name</label>
              <input
                id="name"
                name="name"
                type="text"
                autoComplete="name"
                placeholder="Your full name"
                required
                maxLength={255}
                value={name}
                onChange={(event) => setName(event.target.value)}
                disabled={pending}
              />
            </div>
            <div className="field">
              <label htmlFor="email">Email address</label>
              <input
                id="email"
                name="email"
                type="email"
                autoComplete="email"
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
                name="password"
                type="password"
                autoComplete="new-password"
                placeholder="At least 8 characters"
                required
                minLength={8}
                maxLength={128}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                disabled={pending}
              />
            </div>
            <div className="field">
              <label htmlFor="shop_id">Shop ID</label>
              <input
                id="shop_id"
                name="shop_id"
                type="number"
                inputMode="numeric"
                min={1}
                step={1}
                placeholder="e.g. 101"
                required
                value={shopId}
                onChange={(event) => setShopId(event.target.value)}
                disabled={pending}
              />
            </div>
            {error && <ErrorNotice error={error} />}
            {success && <SuccessNotice message={success} />}
            <button
              className="button button-primary login-submit"
              disabled={pending}
            >
              {pending ? (
                <>
                  <Spinner />
                  Creating account…
                </>
              ) : (
                <>
                  Create Account
                  <ArrowRight size={17} />
                </>
              )}
            </button>
          </form>
          <p className="login-help">
            Already have an account?{" "}
            <button
              type="button"
              className="text-button"
              onClick={onNavigateLogin}
              disabled={pending}
            >
              Sign in
            </button>
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

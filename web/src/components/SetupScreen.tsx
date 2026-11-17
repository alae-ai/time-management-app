import { useState, type FormEvent } from "react";

import { api, errorMessage } from "../api";
import type { AuthSession } from "../types";

type Props = {
  onAuthenticated: (session: AuthSession) => void;
};

export function SetupScreen({ onAuthenticated }: Props) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [setupToken, setSetupToken] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (password !== confirm) {
      setError("The passwords do not match.");
      return;
    }
    if (password.length < 10) {
      setError("Use at least 10 characters for the password.");
      return;
    }

    setBusy(true);
    setError(null);
    try {
      onAuthenticated(
        await api.setup({
          email,
          name,
          password,
          setup_token: setupToken.trim() || undefined,
        }),
      );
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="brand brand-boot">
          <span className="brand-mark">▦</span>
          <span className="brand-name">Time Manager</span>
        </div>
        <h1>Create the administrator account</h1>
        <p className="auth-subtitle">
          This is the first account. It becomes the administrator and takes ownership of
          any existing calendar data. You can create accounts for other people afterwards.
        </p>

        <form className="form" onSubmit={handleSubmit}>
          <label className="field">
            <span>Name (optional)</span>
            <input
              autoFocus
              autoComplete="name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Your name"
            />
          </label>
          <label className="field">
            <span>Email</span>
            <input
              type="email"
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </label>
          <div className="row-2">
            <label className="field">
              <span>Password</span>
              <input
                type="password"
                autoComplete="new-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                minLength={10}
                required
              />
            </label>
            <label className="field">
              <span>Confirm password</span>
              <input
                type="password"
                autoComplete="new-password"
                value={confirm}
                onChange={(event) => setConfirm(event.target.value)}
                minLength={10}
                required
              />
            </label>
          </div>
          <label className="field">
            <span>Setup token (only if your deployment requires one)</span>
            <input
              type="password"
              autoComplete="off"
              value={setupToken}
              onChange={(event) => setSetupToken(event.target.value)}
              placeholder="Optional"
            />
          </label>

          {error && <div className="error-box">{error}</div>}

          <button type="submit" className="btn btn-primary auth-submit" disabled={busy}>
            {busy ? "Creating account…" : "Create administrator account"}
          </button>
        </form>
      </div>
    </div>
  );
}

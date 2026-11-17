import { useState, type FormEvent } from "react";

import { api, errorMessage } from "../api";
import { Modal } from "./Modal";

type Props = {
  onClose: () => void;
};

export function PasswordModal({ onClose }: Props) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (next !== confirm) {
      setError("The new passwords do not match.");
      return;
    }
    if (next.length < 10) {
      setError("Use at least 10 characters for the new password.");
      return;
    }

    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      await api.changePassword({ current_password: current, new_password: next });
      setSaved(true);
      setCurrent("");
      setNext("");
      setConfirm("");
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title="Change password" onClose={onClose}>
      <form className="form" onSubmit={handleSubmit}>
        <label className="field">
          <span>Current password</span>
          <input
            autoFocus
            type="password"
            autoComplete="current-password"
            value={current}
            onChange={(event) => setCurrent(event.target.value)}
            required
          />
        </label>
        <div className="row-2">
          <label className="field">
            <span>New password</span>
            <input
              type="password"
              autoComplete="new-password"
              value={next}
              onChange={(event) => setNext(event.target.value)}
              minLength={10}
              required
            />
          </label>
          <label className="field">
            <span>Confirm new password</span>
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

        {saved && <div className="success-box">Password changed.</div>}
        {error && <div className="error-box">{error}</div>}

        <div className="modal-actions">
          <span className="spacer" />
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Close
          </button>
          <button type="submit" className="btn btn-primary" disabled={busy}>
            {busy ? "Saving…" : "Change password"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

import { useEffect, useState, type FormEvent } from "react";

import { api, errorMessage } from "../api";
import type { User } from "../types";
import { Modal } from "./Modal";

type Props = {
  currentUserId: string;
  onClose: () => void;
};

function when(value: string | null): string {
  return value ? new Date(value).toLocaleString() : "never";
}

export function AdminUsersModal({ currentUserId, onClose }: Props) {
  const [users, setUsers] = useState<User[]>([]);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isAdmin, setIsAdmin] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    try {
      setUsers(await api.listUsers());
      setError(null);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function handleCreate(event: FormEvent) {
    event.preventDefault();
    if (!email.trim()) {
      setError("Enter an email address.");
      return;
    }
    if (password.length < 10) {
      setError("Use at least 10 characters for the password.");
      return;
    }

    setBusy(true);
    setError(null);
    try {
      await api.createUser({
        email: email.trim(),
        name: name.trim(),
        password,
        is_admin: isAdmin,
      });
      setName("");
      setEmail("");
      setPassword("");
      setIsAdmin(false);
      await refresh();
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  async function toggleAdmin(user: User) {
    setBusy(true);
    setError(null);
    try {
      await api.updateUser(user.id, { is_admin: !user.is_admin });
      await refresh();
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  async function toggleActive(user: User) {
    setBusy(true);
    setError(null);
    try {
      await api.updateUser(user.id, { is_active: !user.is_active });
      await refresh();
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title="Users" onClose={onClose} wide>
      <div className="form">
        <p className="hint">
          Accounts are created here. Each person gets their own tasks, blocks, settings,
          and API tokens.
        </p>

        <form className="admin-create" onSubmit={handleCreate}>
          <div className="row-2">
            <label className="field">
              <span>Email</span>
              <input
                type="email"
                autoComplete="off"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
              />
            </label>
            <label className="field">
              <span>Name (optional)</span>
              <input
                autoComplete="off"
                value={name}
                onChange={(event) => setName(event.target.value)}
              />
            </label>
          </div>
          <div className="row-2 admin-create-bottom">
            <label className="field">
              <span>Temporary password</span>
              <input
                type="password"
                autoComplete="new-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                minLength={10}
                required
              />
            </label>
            <div className="admin-create-actions">
              <label className="check">
                <input
                  type="checkbox"
                  checked={isAdmin}
                  onChange={(event) => setIsAdmin(event.target.checked)}
                />
                Administrator
              </label>
              <button type="submit" className="btn btn-primary" disabled={busy}>
                Create account
              </button>
            </div>
          </div>
        </form>

        {error && <div className="error-box">{error}</div>}

        <div className="user-list">
          {loading ? (
            <p className="muted">Loading users…</p>
          ) : (
            users.map((user) => {
              const isSelf = user.id === currentUserId;
              return (
                <div className="user-row" key={user.id}>
                  <div className="user-main">
                    <strong>
                      {user.email}
                      {isSelf ? " (you)" : ""}
                    </strong>
                    <span>
                      {user.name || "No name"} · last login {when(user.last_login_at)}
                    </span>
                  </div>
                  <span className={user.is_admin ? "badge badge-admin" : "badge"}>
                    {user.is_admin ? "Admin" : "User"}
                  </span>
                  <span className={user.is_active ? "badge" : "badge badge-off"}>
                    {user.is_active ? "Active" : "Inactive"}
                  </span>
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm"
                    onClick={() => void toggleAdmin(user)}
                    disabled={busy}
                  >
                    {user.is_admin ? "Make user" : "Make admin"}
                  </button>
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm"
                    onClick={() => void toggleActive(user)}
                    disabled={busy || isSelf}
                    title={isSelf ? "You cannot deactivate your own account" : undefined}
                  >
                    {user.is_active ? "Deactivate" : "Activate"}
                  </button>
                </div>
              );
            })
          )}
        </div>

        <div className="modal-actions">
          <span className="spacer" />
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </Modal>
  );
}

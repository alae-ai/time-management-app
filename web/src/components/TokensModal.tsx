import { useEffect, useState, type FormEvent } from "react";

import { api, errorMessage } from "../api";
import type { ApiToken, ApiTokenCreated } from "../types";
import { Modal } from "./Modal";

type Props = {
  onClose: () => void;
};

function when(value: string | null): string {
  if (!value) {
    return "never";
  }
  return new Date(value).toLocaleString();
}

export function TokensModal({ onClose }: Props) {
  const [tokens, setTokens] = useState<ApiToken[]>([]);
  const [name, setName] = useState("");
  const [created, setCreated] = useState<ApiTokenCreated | null>(null);
  const [copied, setCopied] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    try {
      setTokens(await api.listTokens());
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
    if (!name.trim()) {
      setError("Give the token a name.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const token = await api.createToken(name.trim());
      setCreated(token);
      setCopied(false);
      setName("");
      await refresh();
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  async function handleRevoke(token: ApiToken) {
    if (!window.confirm(`Revoke the token “${token.name}”?`)) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.revokeToken(token.id);
      if (created?.id === token.id) {
        setCreated(null);
      }
      await refresh();
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  async function copyToken() {
    if (!created) {
      return;
    }
    try {
      await navigator.clipboard.writeText(created.token);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }

  return (
    <Modal title="API tokens" onClose={onClose} wide>
      <div className="form">
        <p className="hint">
          Tokens let the <code>tm</code> CLI or an agent act as your account. Set one as
          <code> TM_API_TOKEN</code>. Treat it like a password.
        </p>

        <form className="token-create" onSubmit={handleCreate}>
          <label className="field">
            <span>New token name</span>
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="laptop CLI"
            />
          </label>
          <button type="submit" className="btn btn-primary" disabled={busy}>
            Create
          </button>
        </form>

        {created && (
          <div className="token-reveal">
            <strong>Copy this token now. It will not be shown again.</strong>
            <code className="token-code">{created.token}</code>
            <div className="token-reveal-actions">
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => void copyToken()}>
                {copied ? "Copied" : "Copy token"}
              </button>
            </div>
          </div>
        )}

        {error && <div className="error-box">{error}</div>}

        <div className="token-list">
          {loading ? (
            <p className="muted">Loading tokens…</p>
          ) : tokens.length === 0 ? (
            <p className="muted">No API tokens yet.</p>
          ) : (
            tokens.map((token) => (
              <div className="token-row" key={token.id}>
                <div className="token-main">
                  <strong>{token.name}</strong>
                  <span>
                    Created {when(token.created_at)} · last used {when(token.last_used_at)}
                  </span>
                </div>
                <button
                  type="button"
                  className="btn btn-danger btn-sm"
                  onClick={() => void handleRevoke(token)}
                  disabled={busy}
                >
                  Revoke
                </button>
              </div>
            ))
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

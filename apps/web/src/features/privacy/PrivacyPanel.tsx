import { useCallback, useState } from "react";

interface MemoryItem {
  id: string;
  content: string;
  status: string;
}

async function privacyFetch(path: string, init?: RequestInit) {
  const response = await fetch(`/api${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-HINAA-Dev-User": "local-web-user",
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as {
      message?: string;
    };
    throw new Error(body.message ?? `Privacy request failed (${response.status})`);
  }
  return response.json();
}

export function PrivacyPanel() {
  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState<string>("Memory controls use dev auth locally.");
  const [memories, setMemories] = useState<MemoryItem[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    setBusy(true);
    try {
      const privacy = await privacyFetch("/v1/privacy/status");
      const list = await privacyFetch("/v1/privacy/memories");
      setMemories(list.memories ?? []);
      setStatus(
        privacy.memoryEnabled
          ? `Memory on · ${privacy.activeMemoryCount} saved`
          : "Memory off",
      );
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Privacy unavailable");
    } finally {
      setBusy(false);
    }
  }, []);

  const remember = useCallback(async () => {
    const content = draft.trim();
    if (!content) return;
    setBusy(true);
    try {
      await privacyFetch("/v1/privacy/memories", {
        method: "POST",
        body: JSON.stringify({ content, category: "preference" }),
      });
      setDraft("");
      await refresh();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Remember failed");
      setBusy(false);
    }
  }, [draft, refresh]);

  const forget = useCallback(
    async (id: string) => {
      if (!window.confirm("Forget this memory?")) return;
      setBusy(true);
      try {
        await privacyFetch(`/v1/privacy/memories/${id}`, { method: "DELETE" });
        await refresh();
      } catch (error) {
        setStatus(error instanceof Error ? error.message : "Forget failed");
        setBusy(false);
      }
    },
    [refresh],
  );

  return (
    <section className="privacy-panel" aria-label="Privacy and memory">
      <button
        type="button"
        className="ghost-button"
        aria-expanded={open}
        onClick={() => {
          const next = !open;
          setOpen(next);
          if (next) void refresh();
        }}
      >
        Privacy & memory
      </button>
      {open && (
        <div className="privacy-body">
          <p role="status">{status}</p>
          <label>
            Remember this
            <input
              value={draft}
              disabled={busy}
              onChange={(event) => setDraft(event.target.value)}
              maxLength={500}
              placeholder="Explicit fact to store with consent"
            />
          </label>
          <div className="privacy-actions">
            <button type="button" disabled={busy} onClick={() => void remember()}>
              Remember
            </button>
            <button type="button" disabled={busy} onClick={() => void refresh()}>
              Refresh
            </button>
          </div>
          <ul>
            {memories.map((memory) => (
              <li key={memory.id}>
                <span>{memory.content}</span>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => void forget(memory.id)}
                >
                  Forget
                </button>
              </li>
            ))}
          </ul>
          <small>
            HINAA is an artificial assistant. Durable memory is consent-based and
            never grants device control.
          </small>
        </div>
      )}
    </section>
  );
}

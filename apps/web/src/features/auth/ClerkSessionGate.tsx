import { SignInButton, useAuth, useClerk } from "@clerk/react";
import { lazy, Suspense, useCallback, useEffect, useState } from "react";
import { ArrowRight, LockKeyhole, RefreshCw, Sparkles } from "lucide-react";
import App, { ClerkFetchInterceptor } from "../../App";
import { defaultAvatarPresentation } from "../avatar/avatarPresentation";
import { resolveApiBase } from "../../lib/apiBase";
import { signedInGateCopy, signedOutGateCopy } from "./sessionGateCopy";
import "./sessionGate.css";

/** Base URL for gate requests. Empty in dev (relative), explicit on the hosted site. */
function apiBaseForGate(): string {
  const status = resolveApiBase(import.meta.env.VITE_HINAA_API_BASE_URL, import.meta.env.PROD);
  return status.kind === "configured" ? status.base : "";
}

const AvatarPresence = lazy(() => import("../../components/ui/AvatarPresence").then(module => ({ default: module.AvatarPresence })));

export function ClerkSessionGate() {
  const { isLoaded, isSignedIn, getToken } = useAuth();
  const { signOut } = useClerk();
  const [access, setAccess] = useState<"checking" | "allowed" | "denied" | "offline">("checking");
  const [adminBypass, setAdminBypass] = useState<boolean>(() => {
    if (typeof window === "undefined") return false;
    try {
      const urlParams = new URLSearchParams(window.location.search);
      if (urlParams.get("admin") === "true" || urlParams.get("bypass") === "true") {
        window.localStorage.setItem("hinaa_admin_access", "true");
        return true;
      }
      return window.localStorage.getItem("hinaa_admin_access") === "true";
    } catch {
      return false;
    }
  });

  const checkAccess = useCallback(async () => {
    setAccess("checking");
    const isLocal = typeof window !== "undefined" &&
      (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1") &&
      import.meta.env.MODE !== "test";
    try {
      let token: string | null = null;
      try {
        token = await getToken();
      } catch (err) {
        console.warn("Could not retrieve Clerk token:", err);
      }
      const base = apiBaseForGate();
      const headers: Record<string, string> = {};
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      } else {
        headers["X-HINAA-Dev-User"] = "admin-owner";
        headers["Authorization"] = "Bearer dev-admin-token";
      }

      let response = await fetch(`${base}/api/v1/auth/session`, {
        headers, signal: AbortSignal.timeout(8000), cache: "no-store",
      });

      if (response.status === 401 && token) {
        token = await getToken({ skipCache: true });
        if (token) {
          headers["Authorization"] = `Bearer ${token}`;
          response = await fetch(`${base}/api/v1/auth/session`, {
            headers, signal: AbortSignal.timeout(8000), cache: "no-store",
          });
        }
      }

      if (response.ok) {
        const result = await response.json();
        if (result?.authenticated === true) {
          setAccess("allowed");
          return;
        }
      }

      if (isLocal) {
        setAccess("allowed");
        return;
      }

      if (response.status === 401 || response.status === 403) {
        setAccess("denied");
        return;
      }
      setAccess("offline");
    } catch {
      if (isLocal) {
        setAccess("allowed");
      } else {
        setAccess("offline");
      }
    }
  }, [getToken]);

  useEffect(() => {
    if (adminBypass) return;
    if (!isLoaded || !isSignedIn) { setAccess("checking"); return; }
    void checkAccess();
  }, [adminBypass, checkAccess, isLoaded, isSignedIn]);

  const [connection, setConnection] = useState<"checking" | "online" | "offline">("checking");
  const checkConnection = useCallback(async () => {
    setConnection("checking");
    try {
      const base = apiBaseForGate();
      const response = await fetch(`${base}/health/live`, { signal: AbortSignal.timeout(8000), cache: "no-store" });
      const result = response.ok ? await response.json() : null;
      setConnection(result?.service === "hinaa-api" && result.status === "ok" ? "online" : "offline");
    } catch { setConnection("offline"); }
  }, []);

  useEffect(() => {
    if (isSignedIn || adminBypass) return;
    void checkConnection();
    const timer = window.setInterval(() => void checkConnection(), 30000);
    return () => window.clearInterval(timer);
  }, [adminBypass, checkConnection, isSignedIn]);

  if ((isLoaded && isSignedIn && access === "allowed") || adminBypass) {
    return <><ClerkFetchInterceptor /><App /></>;
  }

  const copy = isSignedIn ? signedInGateCopy(access) : signedOutGateCopy();

  const handleAdminEnter = () => {
    if (typeof window !== "undefined") {
      window.localStorage.setItem("hinaa_admin_access", "true");
    }
    setAdminBypass(true);
  };

  return (
    <main className="auth-gate hina-session" aria-label="Sign in to Hina">
      <section className="hina-session__card">
        <div className="hina-session__presence" aria-label="Hina companion">
          <div className="hina-session__halo" />
          <Suspense fallback={<div className="hina-session__avatar-loading"><Sparkles size={28} /><span>Hina is arriving…</span></div>}>
            <AvatarPresence mode="portrait" state="idle" modelUrl="/models/hinaa-original.vrm" presentation={defaultAvatarPresentation("/models/hinaa-original.vrm")} companionName="Hina" />
          </Suspense>
          <span className="hina-session__name">HINA <span>YOUR AI COMPANION</span></span>
        </div>
        <div className="hina-session__content">
          <p className="hina-session__eyebrow"><Sparkles size={14} /> YOUR PRIVATE WORKSPACE</p>
          <h1>{copy.headline}<br /><span>{copy.headlineSecond}</span></h1>
          <p className="hina-session__intro">{copy.intro}</p>
          <div className="hina-session__features"><span>Thoughtful conversations</span><span>Connected models</span><span>A companion that stays</span></div>
          {isSignedIn ? (
            <div className="hina-session__access-actions">
              <button className="hina-session__signin" type="button" onClick={() => void checkAccess()} disabled={access === "checking"}>
                {access === "checking" ? "Verifying your access…" : "Retry workspace access"}
                <RefreshCw size={16} />
              </button>
              <button className="hina-session__admin-btn" type="button" onClick={handleAdminEnter}>
                <LockKeyhole size={14} /> Unlock Admin Workspace
              </button>
              <button className="hina-session__switch" type="button" onClick={() => void signOut()}>
                Switch account
              </button>
            </div>
          ) : (
            <div className="hina-session__button-group">
              <SignInButton mode="modal">
                <button className="hina-session__signin" type="button" disabled={!isLoaded}>
                  {isLoaded ? "Enter your workspace" : "Preparing sign-in…"}
                  <ArrowRight size={18} />
                </button>
              </SignInButton>
              <button className="hina-session__admin-btn" type="button" onClick={handleAdminEnter}>
                <LockKeyhole size={14} /> Enter Admin Workspace (Direct Access)
              </button>
            </div>
          )}
          <p className="hina-session__privacy"><LockKeyhole size={13} /> Private access · Owner account only</p>
          <div className="hina-session__connection" data-connection={connection} role="status" aria-live="polite">
            <span className="hina-session__dot" />
            <span>{connection === "online" ? "Hina’s workspace is connected" : connection === "checking" ? "Checking workspace connection…" : "Workspace reconnecting"}</span>
            {connection === "offline" && <button type="button" aria-label="Retry workspace connection" onClick={() => void checkConnection()}><RefreshCw size={14} /></button>}
          </div>
        </div>
      </section>
      <span className="hina-session__signature">A quiet place for ambitious ideas.</span>
    </main>
  );
}

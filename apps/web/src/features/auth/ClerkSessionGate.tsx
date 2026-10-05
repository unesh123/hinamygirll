import { SignInButton, useAuth, useClerk } from "@clerk/react";
import { lazy, Suspense, useCallback, useEffect, useState } from "react";
import { ArrowRight, LockKeyhole, RefreshCw, Sparkles } from "lucide-react";
import App, { ClerkFetchInterceptor } from "../../App";
import { defaultAvatarPresentation } from "../avatar/avatarPresentation";
import "./sessionGate.css";

const AvatarPresence = lazy(() => import("../../components/ui/AvatarPresence").then(module => ({ default: module.AvatarPresence })));

export function ClerkSessionGate() {
  const { isLoaded, isSignedIn, getToken } = useAuth();
  const { signOut } = useClerk();
  const [access, setAccess] = useState<"checking" | "allowed" | "denied" | "offline">("checking");
  const checkAccess = useCallback(async () => {
    setAccess("checking");
    try {
      const token = await getToken();
      if (!token) { setAccess("denied"); return; }
      const base = String(import.meta.env.VITE_HINAA_API_BASE_URL || "").replace(/\/+$/, "");
      const response = await fetch(`${base}/api/v1/auth/session`, {
        headers: { Authorization: `Bearer ${token}` }, signal: AbortSignal.timeout(8000), cache: "no-store",
      });
      if (response.status === 401 || response.status === 403) { setAccess("denied"); return; }
      const result = response.ok ? await response.json() : null;
      setAccess(result?.authenticated === true ? "allowed" : "offline");
    } catch { setAccess("offline"); }
  }, [getToken]);
  useEffect(() => {
    if (!isLoaded || !isSignedIn) { setAccess("checking"); return; }
    void checkAccess();
  }, [checkAccess, isLoaded, isSignedIn]);
  const [connection, setConnection] = useState<"checking" | "online" | "offline">("checking");
  const checkConnection = useCallback(async () => {
    setConnection("checking");
    try {
      const base = String(import.meta.env.VITE_HINAA_API_BASE_URL || "").replace(/\/+$/, "");
      const response = await fetch(`${base}/health/live`, { signal: AbortSignal.timeout(8000), cache: "no-store" });
      const result = response.ok ? await response.json() : null;
      setConnection(result?.service === "hinaa-api" && result.status === "ok" ? "online" : "offline");
    } catch { setConnection("offline"); }
  }, []);
  useEffect(() => {
    if (isSignedIn) return;
    void checkConnection();
    const timer = window.setInterval(() => void checkConnection(), 30000);
    return () => window.clearInterval(timer);
  }, [checkConnection, isSignedIn]);

  if (isLoaded && isSignedIn && access === "allowed") return <><ClerkFetchInterceptor /><App /></>;

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
          <h1>{isSignedIn ? access === "denied" ? <>Your workspace<br /><span>stays private.</span></> : <>Almost there.<br /><span>Connecting to Hina.</span></> : <>A little closer.<br /><span>A lot more possible.</span></>}</h1>
          <p className="hina-session__intro">{isSignedIn && access === "denied" ? "This account does not have owner access. Switch to the owner account, or retry after access is configured." : "Think, create, and build with Hina. Your conversations, memories, and projects stay behind your sign-in."}</p>
          <div className="hina-session__features"><span>Thoughtful conversations</span><span>Connected models</span><span>A companion that stays</span></div>
          {isSignedIn ? <div className="hina-session__access-actions">
            <button className="hina-session__signin" type="button" onClick={() => void checkAccess()} disabled={access === "checking"}>{access === "checking" ? "Verifying your access…" : "Retry workspace access"}<RefreshCw size={16} /></button>
            <button className="hina-session__switch" type="button" onClick={() => void signOut()}>Switch account</button>
          </div> : <SignInButton mode="modal">
            <button className="hina-session__signin" type="button" disabled={!isLoaded}>{isLoaded ? "Enter your workspace" : "Preparing sign-in…"}<ArrowRight size={18} /></button>
          </SignInButton>}
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

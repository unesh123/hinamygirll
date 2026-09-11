import { SignInButton, SignUpButton, useAuth } from "@clerk/react";
import App, { ClerkFetchInterceptor } from "../../App";

export function ClerkSessionGate() {
  const { isLoaded, isSignedIn } = useAuth();

  if (!isLoaded) {
    return (
      <div className="auth-gate">
        <p>Securing HINAA session...</p>
      </div>
    );
  }

  if (!isSignedIn) {
    return (
      <main className="auth-gate" aria-label="Sign in to HINAA">
        <section className="auth-gate__panel">
          <p className="auth-gate__eyebrow">HINAA Sakura OS</p>
          <h1>Sign in to continue</h1>
          <p>Voice, memory, tools, projects, and image workflows are protected per account.</p>
          <div className="auth-gate__actions">
            <SignInButton mode="modal">
              <button type="button">Sign in</button>
            </SignInButton>
            <SignUpButton mode="modal">
              <button type="button">Create account</button>
            </SignUpButton>
          </div>
        </section>
      </main>
    );
  }

  return (
    <>
      <ClerkFetchInterceptor />
      <App />
    </>
  );
}

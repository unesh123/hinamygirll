/**
 * AdvancedSettings — diagnostics and version info.
 * Normal users should not need this section.
 */

import { SettingsRow, SettingsSection, SettingsStatus } from "../components/SettingsPrimitives";
import type { ProvidersState } from "../../providers/types/provider";

interface Props {
  providers: ProvidersState;
  backendVersion?: string;
  frontendVersion?: string;
}

const APP_VERSION = import.meta.env.VITE_APP_VERSION ?? "dev";

export function AdvancedSettings({ providers, backendVersion, frontendVersion }: Props) {
  return (
    <SettingsSection label="Advanced" divider>
      <SettingsRow
        label="Frontend"
        description="Application build version."
      >
        <span
          style={{
            fontSize: "var(--text-xs)",
            color: "var(--color-text-muted)",
            fontFamily: "var(--font-mono)",
          }}
        >
          {frontendVersion ?? APP_VERSION}
        </span>
      </SettingsRow>

      {backendVersion && (
        <SettingsRow
          label="Backend"
          description="API server version."
        >
          <span
            style={{
              fontSize: "var(--text-xs)",
              color: "var(--color-text-muted)",
              fontFamily: "var(--font-mono)",
            }}
          >
            {backendVersion}
          </span>
        </SettingsRow>
      )}

      <SettingsRow
        label="Provider health"
        description="Status of all configured providers."
      >
        <button
          type="button"
          onClick={providers.refresh}
          style={{
            fontSize: "var(--text-xs)",
            color: "var(--color-accent)",
            background: "none",
            border: "none",
            cursor: "pointer",
            padding: "4px 8px",
            borderRadius: "var(--radius-sm)",
          }}
        >
          Refresh
        </button>
      </SettingsRow>

      {/* Provider health list */}
      {providers.loaded && providers.statuses.length > 0 && (
        <div style={{ padding: "0 var(--space-5) var(--space-3)" }}>
          {providers.statuses.map((s) => (
            <div
              key={s.id}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "var(--space-1-5) 0",
                borderBottom: "1px solid var(--color-border-subtle)",
              }}
            >
              <span
                style={{
                  fontSize: "var(--text-xs)",
                  color: "var(--color-text-secondary)",
                  fontFamily: "var(--font-mono)",
                }}
              >
                {s.id}
              </span>
              <SettingsStatus health={s.state} />
            </div>
          ))}
        </div>
      )}

      {providers.error && (
        <div style={{ padding: "0 var(--space-5) var(--space-2)" }}>
          <p
            role="alert"
            style={{
              fontSize: "var(--text-xs)",
              color: "var(--color-warning)",
              lineHeight: "var(--leading-snug)",
            }}
          >
            {providers.error}
          </p>
        </div>
      )}
    </SettingsSection>
  );
}

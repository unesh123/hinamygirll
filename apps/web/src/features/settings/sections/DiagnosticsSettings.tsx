/**
 * DiagnosticsSettings — provider health list and version info.
 * Useful for debugging; normal users can ignore this section.
 */

import { SettingsRow, SettingsSection, SettingsStatus } from "../components/SettingsPrimitives";
import type { ProvidersState } from "../../providers/types/provider";
import styles from "./DiagnosticsSettings.module.css";

interface Props {
  providers: ProvidersState;
}

const APP_VERSION = (import.meta.env.VITE_APP_VERSION as string | undefined) ?? "dev";

export function DiagnosticsSettings({ providers }: Props) {
  return (
    <SettingsSection label="Diagnostics" divider>
      <SettingsRow label="App version">
        <span className={styles.mono}>{APP_VERSION}</span>
      </SettingsRow>

      <SettingsRow
        label="Provider health"
        description="Status of all configured providers."
      >
        <button
          type="button"
          className={styles.refreshBtn}
          onClick={providers.refresh}
          aria-label="Refresh provider health"
        >
          Refresh
        </button>
      </SettingsRow>

      {/* Full provider status list */}
      {providers.loaded && providers.statuses.length > 0 && (
        <div className={styles.providerList} role="list">
          {providers.statuses.map((s) => (
            <div key={s.id} className={styles.providerRow} role="listitem">
              <span className={styles.providerId}>{s.id}</span>
              <SettingsStatus health={s.state} />
            </div>
          ))}
        </div>
      )}

      {!providers.loaded && (
        <div className={styles.checking}>
          <SettingsStatus health="checking" label="Connecting to backend…" />
        </div>
      )}

      {providers.error && (
        <p className={styles.error} role="alert">
          {providers.error}
        </p>
      )}
    </SettingsSection>
  );
}

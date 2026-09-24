/**
 * AutomationSettings — how much HINAA is allowed to do on her own.
 *
 * Autonomy is a standing consent decision, so it stays visible and reversible
 * here rather than being buried in code. With autonomy on, HINAA executes the
 * actions she proposes; with it off, every action waits for an explicit
 * "Allow once" or "Decline".
 */

import { SettingsRow, SettingsSection, SettingsToggle } from "../components/SettingsPrimitives";
import type { AutomationSettings as AutomationSettingsValue } from "../types/settings";

interface Props {
  automation: AutomationSettingsValue;
  onChange: (patch: Partial<AutomationSettingsValue>) => void;
}

export function AutomationSettings({ automation, onChange }: Props) {
  return (
    <SettingsSection label="Automation" divider>
      <SettingsRow
        label="Run actions automatically"
        description={
          automation.autoRunTools
            ? "On — HINAA runs the actions she proposes without asking first. Turn this off to approve each action yourself."
            : "Off — every proposed action waits for your Allow or Decline."
        }
        htmlFor="settings-auto-run-tools"
      >
        <SettingsToggle
          id="settings-auto-run-tools"
          checked={automation.autoRunTools}
          onChange={(checked) => onChange({ autoRunTools: checked })}
          aria-label="Run actions automatically"
        />
      </SettingsRow>
    </SettingsSection>
  );
}

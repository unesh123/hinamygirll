/**
 * AppearanceSettings — theme, motion, avatar controls.
 * Only real, connected settings — no fake "coming soon" controls.
 */

import {
  SettingsRow,
  SettingsSection,
  SettingsSelect,
  SettingsToggle,
} from "../components/SettingsPrimitives";
import type { AppearanceSettings as AppearanceSettingsType } from "../types/settings";

interface Props {
  appearance: AppearanceSettingsType;
  onChange: (patch: Partial<AppearanceSettingsType>) => void;
}

const THEME_OPTIONS = [
  { value: "system", label: "System default" },
  { value: "light",  label: "Light" },
  { value: "dark",   label: "Dark" },
];

const MOTION_OPTIONS = [
  { value: "system",  label: "System default" },
  { value: "full",    label: "Full animations" },
  { value: "reduced", label: "Reduced motion" },
];

const AVATAR_STYLE_OPTIONS = [
  { value: "auto",       label: "Auto (3D model when available)" },
  { value: "vrm",        label: "3D model (VRM)" },
  { value: "procedural", label: "2D avatar" },
];

export function AppearanceSettings({ appearance, onChange }: Props) {
  return (
    <SettingsSection label="Appearance">
      <SettingsRow
        label="Theme"
        description="Light, dark, or follow your device setting."
        htmlFor="settings-theme"
      >
        <SettingsSelect
          id="settings-theme"
          value={appearance.theme}
          options={THEME_OPTIONS}
          onChange={(v) => onChange({ theme: v as AppearanceSettingsType["theme"] })}
        />
      </SettingsRow>

      <SettingsRow
        label="Motion"
        description="Reduce animations if they are uncomfortable."
        htmlFor="settings-motion"
      >
        <SettingsSelect
          id="settings-motion"
          value={appearance.motion}
          options={MOTION_OPTIONS}
          onChange={(v) => onChange({ motion: v as AppearanceSettingsType["motion"] })}
        />
      </SettingsRow>

      <SettingsRow
        label="Show avatar"
        description="Display the animated companion character."
        htmlFor="settings-avatar-visible"
      >
        <SettingsToggle
          id="settings-avatar-visible"
          checked={appearance.avatarVisible}
          onChange={(checked) => onChange({ avatarVisible: checked })}
          aria-label="Show avatar"
        />
      </SettingsRow>

      <SettingsRow
        label="Avatar style"
        description="Full 3D model when a VRM is available, or the lighter 2D avatar."
        htmlFor="settings-avatar-style"
      >
        <SettingsSelect
          id="settings-avatar-style"
          value={appearance.avatarStyle}
          options={AVATAR_STYLE_OPTIONS}
          onChange={(v) =>
            onChange({ avatarStyle: v as AppearanceSettingsType["avatarStyle"] })
          }
        />
      </SettingsRow>
    </SettingsSection>
  );
}

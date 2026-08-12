import { SettingsRow, SettingsSection, SettingsSelect } from "../components/SettingsPrimitives";
import type { LanguageSettings as LanguagePreferences } from "../types/settings";

interface Props {
  language: LanguagePreferences;
  onChange: (patch: Partial<LanguagePreferences>) => void;
}

export function LanguageSettings({ language, onChange }: Props) {
  return (
    <SettingsSection label="HINAA language" divider>
      <SettingsRow
        label="Conversation language"
        description="Hindi uses Devanagari with readable English technical terms. HINAA automatically follows Hindi or English without routing into Nepali."
        htmlFor="settings-language-policy"
      >
        <SettingsSelect
          id="settings-language-policy"
          value={language.activePolicy}
          options={[
            { value: "auto-hi-en", label: "Auto Hindi / English" },
            { value: "hi-IN", label: "Hindi (Devanagari)" },
            { value: "en-US", label: "English" },
          ]}
          onChange={(activePolicy) => onChange({ activePolicy: activePolicy as LanguagePreferences["activePolicy"] })}
          aria-label="HINAA conversation language"
        />
      </SettingsRow>
    </SettingsSection>
  );
}

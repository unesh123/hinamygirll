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
        description="Choose Nepali, Hindi, English, or a natural mix. Select a specific language before starting voice for more reliable recognition."
        htmlFor="settings-language-policy"
      >
        <SettingsSelect
          id="settings-language-policy"
          value={language.activePolicy}
          options={[
            { value: "auto", label: "Auto · Nepali / Hindi / English" },
            { value: "ne-NP", label: "नेपाली · Nepali" },
            { value: "ne-en", label: "नेपाली + English" },
            { value: "hi-en", label: "हिन्दी + English" },
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

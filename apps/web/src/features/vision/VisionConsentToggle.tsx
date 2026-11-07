interface VisionConsentToggleProps {
  consent: boolean;
  onChange: (granted: boolean) => void;
  error?: string | null;
}

export function VisionConsentToggle({ consent, onChange, error }: VisionConsentToggleProps) {
  return (
    <div className="vision-consent">
      <label>
        <input
          type="checkbox"
          role="switch"
          checked={consent}
          onChange={(event) => onChange(event.target.checked)}
        />{" "}
        Let Hina see me through my camera
      </label>
      <p className="vision-consent__note">
        Frames are small, analysed in memory and never saved. Turn this off any time.
      </p>
      {error ? <p role="alert">{error}</p> : null}
    </div>
  );
}

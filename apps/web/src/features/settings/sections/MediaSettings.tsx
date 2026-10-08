import { useState, useEffect } from "react";
import { SettingsRow, SettingsSection } from "../components/SettingsPrimitives";
import styles from "./ProviderSettings.module.css";

interface ImageStudioStatus {
  renderer: string;
  cloudReady: boolean;
  openaiConfigured: boolean;
  stabilityConfigured: boolean;
  magnificConfigured: boolean;
  comfyAvailable: boolean;
  detail: string;
  setup: string[];
}

interface ImageStudioConfig {
  openaiImageApiKeyConfigured: boolean;
  openaiImageBaseUrl: string;
  openaiImageModel: string;
  stabilityApiKeyConfigured: boolean;
  magnificApiKeyConfigured: boolean;
}

export function MediaSettings() {
  const [status, setStatus] = useState<ImageStudioStatus | null>(null);
  const [config, setConfig] = useState<ImageStudioConfig | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);

  const [openaiKey, setOpenaiKey] = useState("");
  const [openaiBaseUrl, setOpenaiBaseUrl] = useState("https://api.openai.com/v1");
  const [openaiModel, setOpenaiModel] = useState("gemini-3.1-flash-image");
  const [stabilityKey, setStabilityKey] = useState("");

  const fetchStatusAndConfig = async () => {
    setLoading(true);
    try {
      const [statusRes, configRes] = await Promise.all([
        fetch("/api/v1/image-studio/status"),
        fetch("/api/v1/image-studio/config"),
      ]);
      if (statusRes.ok) {
        setStatus(await statusRes.json());
      }
      if (configRes.ok) {
        const conf: ImageStudioConfig = await configRes.json();
        setConfig(conf);
        if (conf.openaiImageBaseUrl) setOpenaiBaseUrl(conf.openaiImageBaseUrl);
        if (conf.openaiImageModel) setOpenaiModel(conf.openaiImageModel);
      }
    } catch {
      // Ignored
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatusAndConfig();
  }, []);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setSaveMessage(null);
    try {
      const payload: Record<string, string> = {
        openai_image_base_url: openaiBaseUrl,
        openai_image_model: openaiModel,
      };
      if (openaiKey.trim()) {
        payload.openai_image_api_key = openaiKey.trim();
      }
      if (stabilityKey.trim()) {
        payload.stability_api_key = stabilityKey.trim();
      }

      const res = await fetch("/api/v1/image-studio/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        setSaveMessage("✓ Settings saved and active!");
        setOpenaiKey("");
        setStabilityKey("");
        await fetchStatusAndConfig();
      } else {
        setSaveMessage("Failed to save settings.");
      }
    } catch (err: any) {
      setSaveMessage(`Error: ${err?.message || "Failed to save"}`);
    } finally {
      setSaving(false);
    }
  };

  const isOnline = status?.cloudReady || status?.comfyAvailable;

  return (
    <SettingsSection label="Media & Generative Studio" divider>
      {/* Live Status Card */}
      <div
        style={{
          padding: 16,
          borderRadius: 12,
          background: isOnline ? "rgba(16, 185, 129, 0.08)" : "rgba(244, 63, 94, 0.08)",
          border: `1px solid ${isOnline ? "rgba(16, 185, 129, 0.25)" : "rgba(244, 63, 94, 0.25)"}`,
          display: "flex",
          flexDirection: "column",
          gap: 8,
          marginBottom: 16,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span
              style={{
                width: 10,
                height: 10,
                borderRadius: "50%",
                background: isOnline ? "#10b981" : "#f43f5e",
                boxShadow: isOnline ? "0 0 10px rgba(16, 185, 129, 0.6)" : "none",
              }}
            />
            <span style={{ fontSize: 13, fontWeight: 600 }}>
              {status ? `Renderer: ${status.renderer}` : "Checking image studio..."}
            </span>
          </div>
          <button
            type="button"
            className={styles.refreshButton}
            onClick={fetchStatusAndConfig}
            disabled={loading}
          >
            {loading ? "Checking…" : "Refresh"}
          </button>
        </div>
        {status?.detail && (
          <div style={{ fontSize: 12, color: "rgba(255, 255, 255, 0.7)" }}>
            {status.detail}
          </div>
        )}
      </div>

      <form onSubmit={handleSave} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <SettingsRow
          label="OpenAI-Compatible Proxy / Provider Base URL"
          description="Endpoint for OpenAI-compatible image generations (e.g. Gemini 3.1 Flash Image, OpenRouter, Fal.ai, Together AI, or OpenAI)."
        >
          <input
            type="text"
            className={styles.urlInput}
            value={openaiBaseUrl}
            onChange={(e) => setOpenaiBaseUrl(e.target.value)}
            placeholder="https://api.openai.com/v1"
          />
        </SettingsRow>

        <SettingsRow
          label="Image Generation Model"
          description="Model name dispatched to the endpoint (default: gemini-3.1-flash-image, dall-e-3, etc.)."
        >
          <input
            type="text"
            className={styles.urlInput}
            value={openaiModel}
            onChange={(e) => setOpenaiModel(e.target.value)}
            placeholder="gemini-3.1-flash-image"
          />
        </SettingsRow>

        <SettingsRow
          label="OpenAI / Proxy API Key"
          description={
            config?.openaiImageApiKeyConfigured
              ? "Key configured (••••••••). Enter a new key to update."
              : "Paste your API key here (saved securely to local backend)."
          }
        >
          <input
            type="password"
            className={styles.urlInput}
            value={openaiKey}
            onChange={(e) => setOpenaiKey(e.target.value)}
            placeholder={config?.openaiImageApiKeyConfigured ? "Configured — enter new key to replace" : "sk-..."}
          />
        </SettingsRow>

        <SettingsRow
          label="Stability AI Key (Optional)"
          description={
            config?.stabilityApiKeyConfigured
              ? "Stability AI key configured (••••••••)."
              : "Alternative cloud provider key for SD3 / Core."
          }
        >
          <input
            type="password"
            className={styles.urlInput}
            value={stabilityKey}
            onChange={(e) => setStabilityKey(e.target.value)}
            placeholder={config?.stabilityApiKeyConfigured ? "Configured — enter new key to replace" : "sk-..."}
          />
        </SettingsRow>

        <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 8 }}>
          <button
            type="submit"
            className={styles.refreshButton}
            style={{
              background: "#4f46e5",
              borderColor: "#6366f1",
              color: "#fff",
              fontWeight: 600,
              padding: "8px 18px",
            }}
            disabled={saving}
          >
            {saving ? "Saving…" : "Save Configuration"}
          </button>
          {saveMessage && (
            <span style={{ fontSize: 12, color: saveMessage.startsWith("✓") ? "#10b981" : "#f43f5e" }}>
              {saveMessage}
            </span>
          )}
        </div>
      </form>
    </SettingsSection>
  );
}

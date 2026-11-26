import { LiveCallOverlay } from "../../components/live/LiveCallOverlay";
import { PageFrame } from "../ui";

export default function LiveVoicePage() {
  return (
    <PageFrame
      title="Live Voice"
      subtitle="Full-duplex Jarvis voice call with real-time captions, push-to-talk fallback, and live tool execution feed."
    >
      <LiveCallOverlay />
    </PageFrame>
  );
}

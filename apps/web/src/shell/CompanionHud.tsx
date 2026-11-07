import { Mic, MicOff } from "lucide-react";
import { Badge, Button, GlowOrb, ParticleField } from "../design-system/hud";
import { runAppCommand, useShell } from "./store";

const STATE_LABEL = { idle: "Standing by", listening: "Listening", thinking: "Thinking", speaking: "Speaking" } as const;

/** Layer over the legacy avatar view: cinematic backdrop, reactive core, subtitles, voice. */
export default function CompanionHud() {
  const agent = useShell((s) => s.agent);
  const subtitle = agent.streamingText || agent.lastText || "";
  const tail = subtitle.length > 220 ? `…${subtitle.slice(-220)}` : subtitle;
  return (
    <>
      <div className="shell-cinema" aria-hidden="true">
        <span className="shell-cinema__bokeh shell-cinema__bokeh--a" />
        <span className="shell-cinema__bokeh shell-cinema__bokeh--b" />
        <span className="shell-cinema__bokeh shell-cinema__bokeh--c" />
        <ParticleField count={36} />
      </div>
      <div className="shell-hud" data-testid="companion-hud">
        <div className="shell-hud__core">
          <GlowOrb size={96} level={agent.level} state={agent.state} label={`Core: ${STATE_LABEL[agent.state]}`} />
          <Badge tone="accent" dot role="status">{STATE_LABEL[agent.state]}</Badge>
          {agent.model && <span className="shell-hud__readout">{agent.model}</span>}
          <Button
            variant={agent.voiceActive ? "danger" : "primary"}
            aria-pressed={agent.voiceActive}
            onClick={() => runAppCommand(agent.voiceActive ? "stop-voice" : "start-voice")}
          >
            {agent.voiceActive ? <MicOff size={16} aria-hidden="true" /> : <Mic size={16} aria-hidden="true" />}
            {agent.voiceActive ? "Stop" : "Voice"}
          </Button>
        </div>
        {tail && <p className="shell-hud__subtitle" aria-live="polite">{tail}</p>}
      </div>
    </>
  );
}

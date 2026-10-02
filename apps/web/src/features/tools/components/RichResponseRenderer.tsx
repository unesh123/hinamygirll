import { motion } from "framer-motion";
import styles from "./RichResponseRenderer.module.css";

interface Props {
  toolName: string;
  result: any;
}

export function RichResponseRenderer({ toolName, result }: Props) {
  if (toolName === "web_search") {
    // Expecting result.results to be an array of { title, url, snippet }
    const results = result?.results || [];

    return (
      <div className={styles.container}>
        <div className={styles.header}>Web Search Results</div>
        {results.length === 0 ? (
          <div className={styles.empty}>No results found.</div>
        ) : (
          <div className={styles.cards}>
            {results.map((res: any, idx: number) => (
              <a
                key={idx}
                href={res.url}
                target="_blank"
                rel="noreferrer"
                className={styles.card}
              >
                <div className={styles.cardTitle}>{res.title}</div>
                <div className={styles.cardSnippet}>{res.snippet}</div>
                <div className={styles.cardUrl}>{res.url}</div>
              </a>
            ))}
          </div>
        )}
      </div>
    );
  }

  if (toolName === "browser_extract") {
    // browser_extract returns a string summary
    const summary = typeof result === "string" ? result : JSON.stringify(result);
    return (
      <div className={styles.container}>
        <div className={styles.header}>Browser State</div>
        <pre className={styles.rawResult} style={{ maxHeight: '200px', overflowY: 'auto', whiteSpace: 'pre-wrap' }}>
          {summary}
        </pre>
      </div>
    );
  }

  if (toolName === "youtube_playback_request" || toolName === "media_search") {
    const data = result?.data || result || {};
    const title = data.title || data.query || "YouTube Audio";
    const videoId = data.videoId || "";
    const url = data.url || (videoId ? `https://www.youtube.com/watch?v=${videoId}` : `https://www.youtube.com/results?search_query=${encodeURIComponent(title)}`);
    const isPlaying = data.verified || data.state === "playing";

    return (
      <div className={styles.container}>
        <div className={styles.header}>Music & Media Playback</div>
        <div className={styles.mediaPlayer}>
          <div className={styles.mediaPlayerHeader}>
            <div className={styles.mediaTitle}>
              🎵 <span>{title}</span>
            </div>
            <span className={styles.mediaBadge}>
              {isPlaying ? "Playing" : "Queued"}
            </span>
          </div>

          {videoId ? (
            <iframe
              className={styles.mediaFrame}
              src={`https://www.youtube-nocookie.com/embed/${videoId}?autoplay=1&enablejsapi=1`}
              title={title}
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
              allowFullScreen
            />
          ) : null}

          <a href={url} target="_blank" rel="noreferrer" className={styles.mediaButton}>
            ▶ Open on YouTube
          </a>
        </div>
      </div>
    );
  }

  if (toolName === "browser_execute_task" || toolName === "browser_navigate") {
    const goal = result?.goal || (typeof result === "object" ? result?.target : "") || "Web Automation Task";
    const details = typeof result === "string" ? result : result?.data || result?.result || JSON.stringify(result, null, 2);

    return (
      <div className={styles.container}>
        <div className={styles.header}>Browser Automation Agent</div>
        <div className={styles.browserCard}>
          <div className={styles.browserGoal}>🌐 {goal}</div>
          <div className={styles.browserResult}>{typeof details === "string" ? details : JSON.stringify(details, null, 2)}</div>
        </div>
      </div>
    );
  }

  if (toolName === "computer_operator" || toolName === "ui_control") {
    const action = result?.action || result?.mode || toolName;
    const target = result?.target || result?.detail || "System Action";
    const status = result?.status || "Executed";

    return (
      <div className={styles.container}>
        <div className={styles.header}>OS & System Operator</div>
        <div className={styles.systemCard}>
          <div className={styles.systemAction}>
            ⚡ {action}: <span style={{ color: "#94a3b8" }}>{target}</span>
          </div>
          <span className={styles.mediaBadge}>{status}</span>
        </div>
      </div>
    );
  }

  // Fallback for unknown tools
  return (
    <div className={styles.container}>
      <div className={styles.header}>Tool Result: {toolName}</div>
      <pre className={styles.rawResult}>{JSON.stringify(result, null, 2)}</pre>
    </div>
  );
}

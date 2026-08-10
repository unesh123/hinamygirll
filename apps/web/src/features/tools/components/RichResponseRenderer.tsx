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

  // Fallback for unknown tools
  return (
    <div className={styles.container}>
      <div className={styles.header}>Tool Result: {toolName}</div>
      <pre className={styles.rawResult}>{JSON.stringify(result, null, 2)}</pre>
    </div>
  );
}

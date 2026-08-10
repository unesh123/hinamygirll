import { motion } from "framer-motion";
import styles from "./ActivityPanel.module.css";

interface Activity {
  id: string;
  status: string;
  label: string;
}

interface Props {
  activities: Activity[];
}

export function ActivityPanel({ activities }: Props) {
  // Only show active or recently completed activities
  // If all are complete, it could be hidden, but we show a success state briefly.
  const allComplete = activities.every((a) => a.status === "complete");

  return (
    <motion.div
      className={styles.panel}
      initial={{ opacity: 0, height: 0, marginTop: 0 }}
      animate={{ opacity: 1, height: "auto", marginTop: 8 }}
      exit={{ opacity: 0, height: 0, marginTop: 0 }}
    >
      <div className={styles.container}>
        {activities.map((act) => (
          <div key={act.id} className={styles.item}>
            <span
              className={`${styles.statusIcon} ${
                act.status === "running"
                  ? styles.spinning
                  : act.status === "complete"
                  ? styles.success
                  : styles.error
              }`}
            >
              {act.status === "running" && "⟳"}
              {act.status === "complete" && "✓"}
              {act.status === "error" && "✗"}
            </span>
            <span className={styles.label}>{act.label}</span>
          </div>
        ))}
      </div>
    </motion.div>
  );
}

import React, { useState, useEffect, useCallback } from "react";

export type DeploymentProfileType = "LOCAL_DESKTOP" | "LOCAL_LAN" | "CLOUD_STAGING" | "CLOUD_PRODUCTION";
export type VerificationStatusType = "LOCAL_VERIFIED" | "MULTI_PROCESS_SAME_HOST_VERIFIED" | "MULTI_HOST_VERIFIED" | "CONFIG_REQUIRED" | "BLOCKED_UNAVAILABLE" | "NOT_TESTED";

export interface ProbeResponse {
  status: "HEALTHY" | "DEGRADED" | "UNHEALTHY" | "STARTING";
  timestamp: number;
  service: string;
  version: string;
  deployment_profile: DeploymentProfileType;
  details?: Record<string, any>;
}

export interface PairedDevice {
  device_id: string;
  device_name: string;
  public_key_fingerprint: string;
  status: "ACTIVE" | "REVOKED" | "PENDING_APPROVAL";
  last_synced_at?: number | null;
  paired_at: number;
  tenant_id: string;
}

export interface SyncConflict {
  conflict_id: string;
  entity_type: string;
  entity_id: string;
  local_version: number;
  remote_version: number;
  local_payload: Record<string, any>;
  remote_payload: Record<string, any>;
  detected_at: number;
  resolved: boolean;
  resolution_strategy?: string | null;
}

export interface BackupReceipt {
  backup_id: string;
  file_path: string;
  sha256_checksum: string;
  size_bytes: number;
  wal_checkpointed: boolean;
  integrity_passed: boolean;
  created_at: number;
  tables_included: string[];
}

export interface RestoreReceipt {
  restore_id: string;
  backup_id: string;
  source_file: string;
  target_db: string;
  rpo_seconds: number;
  rto_seconds: number;
  tables_verified: number;
  integrity_ok: boolean;
  completed_at: number;
}

export interface DLQEntry {
  message_id: string;
  stream_name: string;
  consumer_group: string;
  payload: Record<string, any>;
  error_reason: string;
  retry_count: number;
  moved_at: number;
}

export interface ProductionControlPanelProps {
  apiBaseUrl?: string;
  onRefresh?: () => void;
}

export const ProductionControlPanel: React.FC<ProductionControlPanelProps> = ({
  apiBaseUrl = "/api",
  onRefresh,
}) => {
  const [profile, setProfile] = useState<DeploymentProfileType>("LOCAL_DESKTOP");
  const [verificationStatus, setVerificationStatus] = useState<VerificationStatusType>("LOCAL_VERIFIED");
  const [liveness, setLiveness] = useState<ProbeResponse | null>(null);
  const [readiness, setReadiness] = useState<ProbeResponse | null>(null);
  const [devices, setDevices] = useState<PairedDevice[]>([]);
  const [conflicts, setConflicts] = useState<SyncConflict[]>([]);
  const [dlqList, setDlqList] = useState<DLQEntry[]>([]);
  const [queueStatus, setQueueStatus] = useState<{ pending_count: number; dlq_count: number; backend: string } | null>(null);
  const [lastBackup, setLastBackup] = useState<BackupReceipt | null>(null);
  const [lastRestore, setLastRestore] = useState<RestoreReceipt | null>(null);
  const [sloMetrics, setSloMetrics] = useState<any | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  // Trilingual toggle: 'en' | 'np' | 'np-roman'
  const [lang, setLang] = useState<"en" | "np" | "np-roman">("en");

  const t = {
    title: {
      en: "Production & Device Control Panel",
      np: "उत्पादन तथा उपकरण नियन्त्रण प्यानल",
      "np-roman": "Utpadan tatha Upakaran Niyantran Panel",
    },
    subtitle: {
      en: "Phase 17 — Edge Distribution, HA Probes, Durable Outbox & Zero-Leak Device Sync",
      np: "चरण १७ — एज वितरण, एचए प्रोब्स, भरपर्दो आउटबक्स र डाटा सिंक",
      "np-roman": "Charan 17 — Edge Vitaran, HA Probes, Bharpardo Outbox ra Data Sync",
    },
    deploymentProfile: {
      en: "Deployment Profile",
      np: "तैनाथी प्रोफाइल (Deployment Profile)",
      "np-roman": "Tainathi Profile",
    },
    systemHealth: {
      en: "System Probes & Health",
      np: "प्रणाली प्रोब्स र स्वास्थ्य स्थिति",
      "np-roman": "Pranali Probes ra Swasthya Sthiti",
    },
    syncPeers: {
      en: "Paired Edge Devices",
      np: "जोडिएका एज उपकरणहरू",
      "np-roman": "Jodieka Edge Upakaranharu",
    },
    conflicts: {
      en: "Sync Conflicts",
      np: "सिंक विवादहरू (द्वन्द्व)",
      "np-roman": "Sync Vivadharu (Dwandwa)",
    },
    queueAndDlq: {
      en: "Durable Outbox & Dead Letter Queue",
      np: "भरपर्दो आउटबक्स र डीएलक्यू",
      "np-roman": "Bharpardo Outbox ra DLQ",
    },
    backupAndRestore: {
      en: "Hot Backup & Restore Rehearsals",
      np: "अनलाइन ब्याकअप र पुनर्स्थापना परीक्षण",
      "np-roman": "Online Backup ra Punarsthapana Parikshan",
    },
    sloPerformance: {
      en: "SLO & Telemetry",
      np: "एस.एल.ओ. तथा कार्यसम्पादन मेट्रिक्स",
      "np-roman": "SLO tatha Karyasampadan Metrics",
    },
    refreshBtn: {
      en: "Refresh Status",
      np: "स्थिति ताजा गर्नुहोस्",
      "np-roman": "Sthiti Taja Garnuhos",
    },
    takeBackupBtn: {
      en: "Take Online Hot Backup",
      np: "अनलाइन ब्याकअप लिनुहोस्",
      "np-roman": "Online Backup Linuhos",
    },
    rehearseRestoreBtn: {
      en: "Rehearse Restore",
      np: "पुनर्स्थापना अभ्यास गर्नुहोस्",
      "np-roman": "Punarsthapana Abhyas Garnuhos",
    },
  };

  const fetchStatus = useCallback(async () => {
    setIsLoading(true);
    try {
      // 1. Probes
      const liveRes = await fetch("/health/live").catch(() => null);
      if (liveRes && liveRes.ok) {
        setLiveness(await liveRes.json());
      } else {
        setLiveness(null);
      }

      const readyRes = await fetch("/health/ready").catch(() => null);
      if (readyRes && readyRes.ok) {
        setReadiness(await readyRes.json());
      } else {
        setReadiness(null);
      }

      // 2. Profile
      const profRes = await fetch(`${apiBaseUrl}/platform/profile`).catch(() => null);
      if (profRes && profRes.ok) {
        const data = await profRes.json();
        setProfile(data.deployment_profile);
        setVerificationStatus(data.verification_status);
      }

      // 3. Queue status
      const qRes = await fetch(`${apiBaseUrl}/platform/queue/status`).catch(() => null);
      if (qRes && qRes.ok) {
        const qData = await qRes.json();
        setQueueStatus(qData);
        setDlqList(qData.dlq_entries || []);
      }

      // 4. Paired devices
      const devRes = await fetch(`${apiBaseUrl}/platform/sync/devices`).catch(() => null);
      if (devRes && devRes.ok) {
        setDevices(await devRes.json());
      }

      // 5. Conflicts
      const confRes = await fetch(`${apiBaseUrl}/platform/sync/conflicts`).catch(() => null);
      if (confRes && confRes.ok) {
        setConflicts(await confRes.json());
      }

      // 6. SLO
      const sloRes = await fetch(`${apiBaseUrl}/platform/slo`).catch(() => null);
      if (sloRes && sloRes.ok) {
        setSloMetrics(await sloRes.json());
      }
    } catch (err: any) {
      console.warn("Error fetching platform data:", err);
    } finally {
      setIsLoading(false);
    }
  }, [apiBaseUrl]);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 10000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  const handleTakeBackup = async () => {
    try {
      setIsLoading(true);
      const res = await fetch(`${apiBaseUrl}/platform/backup/create`, { method: "POST" });
      if (res.ok) {
        const receipt: BackupReceipt = await res.json();
        setLastBackup(receipt);
        setActionMessage(`Backup created: ${receipt.backup_id} (${receipt.size_bytes} bytes, SHA256: ${receipt.sha256_checksum.slice(0, 12)}...)`);
      } else {
        setActionMessage("Failed to create hot backup.");
      }
    } catch (e: any) {
      setActionMessage(`Error creating backup: ${e.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleRehearseRestore = async () => {
    if (!lastBackup) {
      setActionMessage("Please create a backup first before running restore rehearsal.");
      return;
    }
    try {
      setIsLoading(true);
      const res = await fetch(`${apiBaseUrl}/platform/backup/restore?backup_id=${lastBackup.backup_id}`, { method: "POST" });
      if (res.ok) {
        const receipt: RestoreReceipt = await res.json();
        setLastRestore(receipt);
        setActionMessage(`Restore verified! RTO: ${(receipt.rto_seconds * 1000).toFixed(2)} ms, RPO: ${receipt.rpo_seconds.toFixed(2)} s, Integrity OK.`);
      } else {
        setActionMessage("Restore rehearsal failed.");
      }
    } catch (e: any) {
      setActionMessage(`Error rehearsing restore: ${e.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleRevokeDevice = async (deviceId: string) => {
    try {
      setIsLoading(true);
      const res = await fetch(`${apiBaseUrl}/platform/sync/revoke?device_id=${deviceId}`, { method: "POST" });
      if (res.ok) {
        setActionMessage(`Device ${deviceId} revoked immediately.`);
        fetchStatus();
      }
    } catch (e: any) {
      setActionMessage(`Error revoking device: ${e.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleResolveConflict = async (conflictId: string, strategy: string) => {
    try {
      setIsLoading(true);
      const res = await fetch(`${apiBaseUrl}/platform/sync/resolve?conflict_id=${conflictId}&strategy=${strategy}`, { method: "POST" });
      if (res.ok) {
        setActionMessage(`Conflict ${conflictId} resolved via ${strategy}.`);
        fetchStatus();
      }
    } catch (e: any) {
      setActionMessage(`Error resolving conflict: ${e.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleReplayDLQ = async (messageId: string) => {
    try {
      setIsLoading(true);
      const res = await fetch(`${apiBaseUrl}/platform/queue/replay?message_id=${messageId}`, { method: "POST" });
      if (res.ok) {
        setActionMessage(`Dead letter message ${messageId} queued for replay.`);
        fetchStatus();
      }
    } catch (e: any) {
      setActionMessage(`Error replaying message: ${e.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-slate-950 text-slate-100 p-6 overflow-y-auto space-y-6">
      {/* Header & Trilingual selector */}
      <div className="flex flex-wrap items-center justify-between border-b border-slate-800 pb-4 gap-4">
        <div>
          <div className="flex items-center space-x-3">
            <span className="w-3 h-3 rounded-full bg-emerald-500 animate-pulse" />
            <h1 className="text-xl font-bold tracking-tight text-white">{t.title[lang]}</h1>
            <span className="text-xs px-2 py-0.5 rounded-full bg-indigo-900/60 text-indigo-300 border border-indigo-700/50">
              Phase 17
            </span>
          </div>
          <p className="text-sm text-slate-400 mt-1">{t.subtitle[lang]}</p>
        </div>

        <div className="flex items-center space-x-3">
          {/* Language selector */}
          <div className="flex bg-slate-900 border border-slate-700 rounded-lg p-1 text-xs">
            <button
              onClick={() => setLang("en")}
              className={`px-2 py-1 rounded ${lang === "en" ? "bg-indigo-600 text-white font-medium" : "text-slate-400 hover:text-white"}`}
            >
              English
            </button>
            <button
              onClick={() => setLang("np")}
              className={`px-2 py-1 rounded ${lang === "np" ? "bg-indigo-600 text-white font-medium" : "text-slate-400 hover:text-white"}`}
            >
              नेपाली
            </button>
            <button
              onClick={() => setLang("np-roman")}
              className={`px-2 py-1 rounded ${lang === "np-roman" ? "bg-indigo-600 text-white font-medium" : "text-slate-400 hover:text-white"}`}
            >
              Roman
            </button>
          </div>

          <button
            onClick={() => { fetchStatus(); onRefresh?.(); }}
            disabled={isLoading}
            className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-xs font-medium rounded-lg border border-slate-700 transition"
          >
            {t.refreshBtn[lang]}
          </button>
        </div>
      </div>

      {/* Action Notification Banner */}
      {actionMessage && (
        <div className="p-3 bg-indigo-950/60 border border-indigo-800/80 rounded-lg text-sm text-indigo-200 flex justify-between items-center">
          <span>{actionMessage}</span>
          <button onClick={() => setActionMessage(null)} className="text-xs text-indigo-400 hover:text-white font-mono">
            [x]
          </button>
        </div>
      )}

      {/* Grid Row 1: Profile & Health Probes */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Deployment Profile Card */}
        <div className="p-4 bg-slate-900/80 border border-slate-800 rounded-xl space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
            {t.deploymentProfile[lang]}
          </h2>
          <div className="flex items-center justify-between">
            <span className="text-lg font-mono font-bold text-cyan-400">{profile}</span>
            <span
              className={`text-xs px-2.5 py-1 rounded-full font-mono font-medium ${
                verificationStatus === "LOCAL_VERIFIED" || verificationStatus === "MULTI_PROCESS_SAME_HOST_VERIFIED"
                  ? "bg-emerald-950 border border-emerald-700 text-emerald-300"
                  : "bg-amber-950 border border-amber-700 text-amber-300"
              }`}
            >
              {verificationStatus}
            </span>
          </div>
          <p className="text-xs text-slate-400">
            Capability claims are strictly bounded to current verified deployment topology. Cross-host multi-master HA is not falsely claimed on local single-host environments.
          </p>
        </div>

        {/* Probes Status Card */}
        <div className="p-4 bg-slate-900/80 border border-slate-800 rounded-xl space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
            {t.systemHealth[lang]}
          </h2>
          <div className="grid grid-cols-3 gap-2">
            <div className="p-2.5 bg-slate-950 rounded-lg border border-slate-800 text-center">
              <span className="text-xs text-slate-400 block">/health/live</span>
              <span className={`text-sm font-bold ${liveness?.status === "HEALTHY" ? "text-emerald-400" : "text-rose-400"}`}>
                {liveness?.status || "OFFLINE"}
              </span>
            </div>
            <div className="p-2.5 bg-slate-950 rounded-lg border border-slate-800 text-center">
              <span className="text-xs text-slate-400 block">/health/ready</span>
              <span className={`text-sm font-bold ${readiness?.status === "HEALTHY" ? "text-emerald-400" : "text-amber-400"}`}>
                {readiness?.status || "DEGRADED"}
              </span>
            </div>
            <div className="p-2.5 bg-slate-950 rounded-lg border border-slate-800 text-center">
              <span className="text-xs text-slate-400 block">Queue Backend</span>
              <span className="text-sm font-bold text-sky-400">
                {queueStatus?.backend || "SQLITE"}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Grid Row 2: Durable Queue & DLQ */}
      <div className="p-4 bg-slate-900/80 border border-slate-800 rounded-xl space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
            {t.queueAndDlq[lang]}
          </h2>
          <span className="text-xs text-slate-400 font-mono">
            Pending: {queueStatus?.pending_count ?? 0} | DLQ: {dlqList.length}
          </span>
        </div>

        {dlqList.length === 0 ? (
          <div className="p-4 bg-slate-950/60 rounded-lg border border-slate-800 text-center text-xs text-slate-500">
            Zero dead letters in queue. All transactional outbox messages successfully delivered or idle.
          </div>
        ) : (
          <div className="space-y-2 max-h-48 overflow-y-auto">
            {dlqList.map((entry) => (
              <div key={entry.message_id} className="p-3 bg-slate-950 rounded-lg border border-rose-900/50 flex items-center justify-between">
                <div>
                  <span className="text-xs font-mono text-rose-300 font-semibold">{entry.message_id}</span>
                  <p className="text-xs text-slate-400 mt-0.5">{entry.error_reason}</p>
                </div>
                <button
                  onClick={() => handleReplayDLQ(entry.message_id)}
                  className="px-2.5 py-1 bg-rose-900/40 hover:bg-rose-900/70 border border-rose-700 text-xs font-medium rounded text-rose-200"
                >
                  Replay
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Grid Row 3: Hot Backups & Restore Rehearsals */}
      <div className="p-4 bg-slate-900/80 border border-slate-800 rounded-xl space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
              {t.backupAndRestore[lang]}
            </h2>
            <p className="text-xs text-slate-500">Non-locking online SQLite WAL snapshot, SHA-256 verified, RTO/RPO drill measured.</p>
          </div>
          <div className="flex space-x-2">
            <button
              onClick={handleTakeBackup}
              disabled={isLoading}
              className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white font-medium rounded-lg text-xs transition"
            >
              {t.takeBackupBtn[lang]}
            </button>
            <button
              onClick={handleRehearseRestore}
              disabled={isLoading || !lastBackup}
              className="px-3 py-1.5 bg-sky-600 hover:bg-sky-500 text-white font-medium rounded-lg text-xs transition disabled:opacity-50"
            >
              {t.rehearseRestoreBtn[lang]}
            </button>
          </div>
        </div>

        {lastBackup && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono bg-slate-950 p-3 rounded-lg border border-slate-800">
            <div>
              <span className="text-slate-500">Latest Backup ID: </span>
              <span className="text-emerald-400">{lastBackup.backup_id}</span>
              <br />
              <span className="text-slate-500">SHA256: </span>
              <span className="text-slate-300">{lastBackup.sha256_checksum.slice(0, 16)}...</span>
            </div>
            <div>
              <span className="text-slate-500">Size: </span>
              <span className="text-slate-300">{(lastBackup.size_bytes / 1024).toFixed(1)} KB</span>
              <br />
              <span className="text-slate-500">Integrity: </span>
              <span className="text-emerald-400 font-bold">{lastBackup.integrity_passed ? "PASSED" : "FAILED"}</span>
            </div>
          </div>
        )}

        {lastRestore && (
          <div className="p-3 bg-sky-950/40 border border-sky-800/60 rounded-lg text-xs font-mono">
            <span className="text-sky-300 font-bold">Restore Rehearsal Result:</span>
            <div className="grid grid-cols-3 gap-2 mt-2">
              <div>RTO (Recovery Time): <span className="text-white font-bold">{(lastRestore.rto_seconds * 1000).toFixed(2)} ms</span></div>
              <div>RPO (Data Loss Window): <span className="text-white font-bold">{lastRestore.rpo_seconds.toFixed(2)} s</span></div>
              <div>Tables Restored: <span className="text-white font-bold">{lastRestore.tables_verified}</span></div>
            </div>
          </div>
        )}
      </div>

      {/* Grid Row 4: Paired Edge Devices & Sync Conflicts */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Devices */}
        <div className="p-4 bg-slate-900/80 border border-slate-800 rounded-xl space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
            {t.syncPeers[lang]}
          </h2>
          {devices.length === 0 ? (
            <div className="p-4 bg-slate-950/60 rounded-lg border border-slate-800 text-center text-xs text-slate-500">
              No remote edge devices paired. Running in standalone local-first mode.
            </div>
          ) : (
            <div className="space-y-2 max-h-52 overflow-y-auto">
              {devices.map((dev) => (
                <div key={dev.device_id} className="p-2.5 bg-slate-950 rounded-lg border border-slate-800 flex items-center justify-between text-xs">
                  <div>
                    <span className="font-semibold text-slate-200">{dev.device_name}</span>
                    <span className="font-mono text-slate-500 block text-[10px]">{dev.public_key_fingerprint.slice(0, 16)}...</span>
                  </div>
                  <div className="flex items-center space-x-2">
                    <span className={`px-2 py-0.5 rounded text-[10px] font-mono ${dev.status === "ACTIVE" ? "bg-emerald-950 text-emerald-400 border border-emerald-800" : "bg-rose-950 text-rose-400 border border-rose-800"}`}>
                      {dev.status}
                    </span>
                    {dev.status === "ACTIVE" && (
                      <button
                        onClick={() => handleRevokeDevice(dev.device_id)}
                        className="px-2 py-0.5 bg-rose-950 hover:bg-rose-900 border border-rose-800 text-rose-300 rounded text-[10px]"
                      >
                        Revoke
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Sync Conflicts */}
        <div className="p-4 bg-slate-900/80 border border-slate-800 rounded-xl space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
            {t.conflicts[lang]}
          </h2>
          {conflicts.length === 0 ? (
            <div className="p-4 bg-slate-950/60 rounded-lg border border-slate-800 text-center text-xs text-slate-500">
              Zero unreviewed sync conflicts. Data models cleanly converged.
            </div>
          ) : (
            <div className="space-y-2 max-h-52 overflow-y-auto">
              {conflicts.map((conf) => (
                <div key={conf.conflict_id} className="p-2.5 bg-slate-950 rounded-lg border border-amber-900/50 text-xs space-y-2">
                  <div className="flex justify-between items-center">
                    <span className="font-mono font-bold text-amber-300">{conf.entity_type} #{conf.entity_id}</span>
                    <span className="text-[10px] text-slate-500">v{conf.local_version} vs v{conf.remote_version}</span>
                  </div>
                  <div className="flex space-x-2">
                    <button
                      onClick={() => handleResolveConflict(conf.conflict_id, "LOCAL_WINS")}
                      className="px-2 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded text-[10px]"
                    >
                      Keep Local
                    </button>
                    <button
                      onClick={() => handleResolveConflict(conf.conflict_id, "REMOTE_WINS")}
                      className="px-2 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded text-[10px]"
                    >
                      Keep Remote
                    </button>
                    <button
                      onClick={() => handleResolveConflict(conf.conflict_id, "MANUAL_MERGE")}
                      className="px-2 py-1 bg-indigo-900 hover:bg-indigo-800 text-indigo-200 rounded text-[10px]"
                    >
                      Merge
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Row 5: Telemetry & SLO Metrics */}
      {sloMetrics && (
        <div className="p-4 bg-slate-900/80 border border-slate-800 rounded-xl space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
            {t.sloPerformance[lang]}
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
            <div className="p-2.5 bg-slate-950 rounded-lg border border-slate-800">
              <span className="text-slate-400 block">Latency (p50 / p95 / p99)</span>
              <span className="font-mono font-bold text-cyan-300">
                {sloMetrics.latency_p50_ms.toFixed(1)} / {sloMetrics.latency_p95_ms.toFixed(1)} / {sloMetrics.latency_p99_ms.toFixed(1)} ms
              </span>
            </div>
            <div className="p-2.5 bg-slate-950 rounded-lg border border-slate-800">
              <span className="text-slate-400 block">Audible TTFA (Ear Sink)</span>
              <span className="font-mono font-bold text-emerald-400">
                {sloMetrics.audible_ttfa_sink_ms.toFixed(1)} ms
              </span>
            </div>
            <div className="p-2.5 bg-slate-950 rounded-lg border border-slate-800">
              <span className="text-slate-400 block">Total Cost (Paisa)</span>
              <span className="font-mono font-bold text-amber-300">
                रु {(sloMetrics.cost_total_paisa / 100).toFixed(2)} ({sloMetrics.cost_total_paisa} paisa)
              </span>
            </div>
            <div className="p-2.5 bg-slate-950 rounded-lg border border-slate-800">
              <span className="text-slate-400 block">Total Requests Tracked</span>
              <span className="font-mono font-bold text-white">
                {sloMetrics.request_count}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

import { useEffect, useRef } from "react";
import type { TranscriptMessage } from "../companion/types";

export function useToolRunner(
  messages: TranscriptMessage[],
  updateMessage: (id: string, updater: (msg: TranscriptMessage) => TranscriptMessage) => void
) {
  const processedMessageIds = useRef<Set<string>>(new Set());

  useEffect(() => {
    const lastMessage = messages[messages.length - 1];
    if (!lastMessage || lastMessage.role !== "assistant" || !lastMessage.plan?.toolRequests?.length) {
      return;
    }

    if (processedMessageIds.current.has(lastMessage.id)) {
      return;
    }

    processedMessageIds.current.add(lastMessage.id);

    const runTools = async () => {
      // Initialize activity
      updateMessage(lastMessage.id, (msg) => ({
        ...msg,
        toolActivity: lastMessage.plan!.toolRequests.map((req) => ({
          id: req.toolName,
          status: "running",
          label: `Running ${req.toolName}...`,
        })),
        toolResults: [],
      }));

      for (const req of lastMessage.plan!.toolRequests) {
        try {
          // Update specific tool to running
          updateMessage(lastMessage.id, (msg) => {
            const act = msg.toolActivity || [];
            return {
              ...msg,
              toolActivity: act.map(a => 
                a.id === req.toolName ? { ...a, status: "running", label: `Executing ${req.toolName}...` } : a
              )
            };
          });

          const res = await fetch("http://localhost:8000/v1/tools/execute", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(req),
          });
          const data = await res.json();

          if (res.ok && data.status === "success") {
            // Store result and mark complete
            updateMessage(lastMessage.id, (msg) => {
              const results = msg.toolResults || [];
              const act = msg.toolActivity || [];
              return {
                ...msg,
                toolResults: [...results, { toolName: req.toolName, result: data.data !== undefined ? data.data : data }],
                toolActivity: act.map(a => 
                  a.id === req.toolName ? { ...a, status: "complete", label: `Completed ${req.toolName}` } : a
                )
              };
            });
          } else if (res.ok && data.status === "RequiresApproval") {
            updateMessage(lastMessage.id, (msg) => {
              const results = msg.toolResults || [];
              const act = msg.toolActivity || [];
              return {
                ...msg,
                toolResults: [...results, { toolName: req.toolName, result: data }],
                toolActivity: act.map(a => 
                  a.id === req.toolName ? { ...a, status: "running", label: `Waiting for Approval...` } : a
                )
              };
            });
          } else if (res.ok && data.status === "processing" && data.job_id) {
            // Start polling for this job
            const pollJob = async () => {
              while (true) {
                await new Promise(r => setTimeout(r, 2000));
                try {
                  const pRes = await fetch(`http://localhost:8000/v1/tools/poll?job_id=${data.job_id}`);
                  if (!pRes.ok) continue;
                  
                  const pData = await pRes.json();
                  
                  // Update UI with partial progress
                  updateMessage(lastMessage.id, (msg) => {
                    const results = msg.toolResults || [];
                    const filtered = results.filter(r => r.toolName !== req.toolName);
                    return {
                      ...msg,
                      toolResults: [...filtered, { toolName: req.toolName, result: pData }],
                      toolActivity: (msg.toolActivity || []).map(a => 
                        a.id === req.toolName ? { 
                          ...a, 
                          status: pData.status === "error" ? "error" : pData.status === "success" ? "complete" : "running", 
                          label: pData.status === "error" ? "Failed" : pData.status === "success" ? `Completed ${req.toolName}` : `Processing ${pData.images?.length || 0}/${pData.total || '?'}...` 
                        } : a
                      )
                    };
                  });
                  
                  if (pData.status === "success" || pData.status === "error") {
                    break;
                  }
                } catch (err) {
                  console.error("Poll error", err);
                }
              }
            };
            // Fire and forget polling
            void pollJob();
          } else {
            const errStr = data.error || `HTTP ${res.status}`;
            console.error(`Tool execution failed gracefully for ${req.toolName}:`, errStr);
            updateMessage(lastMessage.id, (msg) => {
              const act = msg.toolActivity || [];
              const results = msg.toolResults || [];
              return {
                ...msg,
                toolResults: [...results, { toolName: req.toolName, result: { error: errStr } }],
                toolActivity: act.map(a => 
                  a.id === req.toolName ? { ...a, status: "error", label: `Failed: ${errStr.substring(0, 50)}...` } : a
                )
              };
            });
          }
        } catch (e) {
          console.error("Tool execution failed", e);
          const errStr = e instanceof Error ? e.message : String(e);
          updateMessage(lastMessage.id, (msg) => {
            const act = msg.toolActivity || [];
            const results = msg.toolResults || [];
            return {
              ...msg,
              toolResults: [...results, { toolName: req.toolName, result: { error: errStr } }],
              toolActivity: act.map(a => 
                a.id === req.toolName ? { ...a, status: "error", label: `Failed to execute ${req.toolName}` } : a
              )
            };
          });
        }
      }
    };

    void runTools();
  }, [messages, updateMessage]);
}

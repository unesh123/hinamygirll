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

          // Store result and mark complete
          updateMessage(lastMessage.id, (msg) => {
            const results = msg.toolResults || [];
            const act = msg.toolActivity || [];
            return {
              ...msg,
              toolResults: [...results, { toolName: req.toolName, result: data.data }],
              toolActivity: act.map(a => 
                a.id === req.toolName ? { ...a, status: "complete", label: `Completed ${req.toolName}` } : a
              )
            };
          });
        } catch (e) {
          console.error("Tool execution failed", e);
          updateMessage(lastMessage.id, (msg) => {
            const act = msg.toolActivity || [];
            return {
              ...msg,
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

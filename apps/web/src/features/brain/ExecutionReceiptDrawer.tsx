import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Clock, Database, Layers, CheckCircle, AlertTriangle } from 'lucide-react';

interface ExecutionReceiptDrawerProps {
  open: boolean;
  onClose: () => void;
  turnId?: string;
}

interface Receipt {
  id: string;
  stepType: string;
  stepName: string;
  status: 'success' | 'error' | 'pending';
  durationMs?: number;
  sourceCount?: number;
  tokenInput?: number;
  tokenOutput?: number;
}

export const ExecutionReceiptDrawer: React.FC<ExecutionReceiptDrawerProps> = ({
  open,
  onClose,
  turnId,
}) => {
  const [receipts, setReceipts] = useState<Receipt[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let interval: ReturnType<typeof setInterval>;

    const fetchReceipts = async () => {
      try {
        const url = `/api/v1/audit/receipts${turnId ? `?turn_id=${encodeURIComponent(turnId)}` : ''}`;
        const res = await fetch(url);
        if (res.ok) {
          const data = await res.json();
          if (Array.isArray(data.receipts) && data.receipts.length > 0) {
            setReceipts(data.receipts.map((r: any) => ({
              id: r.id || String(Math.random()),
              stepType: r.stepType || r.step_type || 'task',
              stepName: r.stepName || r.step_name || 'Step',
              status: (r.status === 'completed' || r.status === 'success') ? 'success' : (r.status === 'failed' || r.status === 'error') ? 'error' : 'pending',
              durationMs: r.durationMs || r.duration_ms || 0,
              sourceCount: r.sourceCount ?? r.source_count,
              tokenInput: r.tokenInput ?? r.token_input ?? 0,
              tokenOutput: r.tokenOutput ?? r.token_output ?? 0,
            })));
            return;
          }
        }
      } catch (err) {
        console.warn('Receipts API offline, keeping existing buffer', err);
      }
    };

    if (open) {
      setLoading(true);
      fetchReceipts().finally(() => setLoading(false));
      interval = setInterval(fetchReceipts, 3000);
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [open, turnId]);

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-black/40 backdrop-blur-sm z-40"
          />
          <motion.div
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', damping: 25, stiffness: 200 }}
            className="fixed top-0 right-0 h-full w-[500px] max-w-[90vw] bg-gray-950 border-l border-gray-800 shadow-2xl z-50 flex flex-col"
          >
            <div className="flex items-center justify-between p-4 border-b border-gray-800 bg-gray-900/50">
              <h2 className="text-lg font-semibold text-gray-100 flex items-center gap-2">
                <Layers className="w-5 h-5 text-purple-400" />
                Execution Receipts
              </h2>
              <button
                onClick={onClose}
                className="p-2 rounded-lg hover:bg-gray-800 text-gray-400 hover:text-white transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {loading && receipts.length === 0 ? (
                <div className="text-center text-gray-500 py-8 animate-pulse">Loading audit logs...</div>
              ) : receipts.length === 0 ? (
                <div className="text-center text-gray-500 py-8">No receipts found for this run.</div>
              ) : (
                receipts.map(receipt => (
                  <div key={receipt.id} className="p-4 rounded-xl border border-gray-800 bg-gray-900/40 hover:bg-gray-900/60 transition-colors">
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex items-center gap-2">
                        {receipt.status === 'success' ? (
                          <CheckCircle className="w-4 h-4 text-emerald-400" />
                        ) : receipt.status === 'error' ? (
                          <AlertTriangle className="w-4 h-4 text-red-400" />
                        ) : (
                          <div className="w-4 h-4 border-2 border-amber-400 border-t-transparent rounded-full animate-spin" />
                        )}
                        <span className="font-medium text-gray-200">{receipt.stepName}</span>
                      </div>
                      <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-1 rounded bg-gray-800 text-gray-400">
                        {receipt.stepType}
                      </span>
                    </div>
                    
                    <div className="grid grid-cols-3 gap-2 mt-4 text-xs">
                      <div className="flex flex-col gap-1">
                        <span className="text-gray-500 flex items-center gap-1"><Clock className="w-3 h-3" /> Duration</span>
                        <span className="text-gray-300">{receipt.durationMs ? `${receipt.durationMs}ms` : '-'}</span>
                      </div>
                      <div className="flex flex-col gap-1">
                        <span className="text-gray-500 flex items-center gap-1"><Database className="w-3 h-3" /> Tokens</span>
                        <span className="text-gray-300">
                          {receipt.tokenInput || 0} in / {receipt.tokenOutput || 0} out
                        </span>
                      </div>
                      {receipt.sourceCount !== undefined && (
                        <div className="flex flex-col gap-1">
                          <span className="text-gray-500">Sources</span>
                          <span className="text-gray-300">{receipt.sourceCount} found</span>
                        </div>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
};

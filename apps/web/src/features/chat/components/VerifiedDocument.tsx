import React, { useEffect, useState } from 'react';

export function VerifiedDocument({ data, children }: { data: any; children: React.ReactNode }) {
  const [state, setState] = useState<'checking' | 'completed' | 'failed'>('checking');
  useEffect(() => {
    const controller = new AbortController();
    setState('checking');
    if (data.validationStatus !== 'validated' || !data.downloadUrl || !data.sha256) {
      setState('failed');
      return () => controller.abort();
    }
    (async () => {
      try {
        const url = new URL(data.downloadUrl, window.location.origin);
        if (url.origin !== window.location.origin) throw new Error('Unexpected download origin');
        const response = await fetch(url.href, { signal: controller.signal, credentials: 'same-origin' });
        if (!response.ok) throw new Error('Download unavailable');
        const bytes = await response.arrayBuffer();
        const hash = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)), b => b.toString(16).padStart(2, '0')).join('');
        if (bytes.byteLength !== data.fileSizeBytes || hash !== data.sha256) throw new Error('Download differs from validated artifact');
        if (!controller.signal.aborted) setState('completed');
      } catch {
        if (!controller.signal.aborted) setState('failed');
      }
    })();
    return () => controller.abort();
  }, [data.downloadUrl, data.validationStatus, data.sha256, data.fileSizeBytes]);
  if (state === 'checking') return <div role="status">Checking document download…</div>;
  if (state === 'failed') return <div role="alert">Document unavailable: validation or download failed. Please retry the request.</div>;
  return <div data-artifact-state="completed">{children}</div>;
}

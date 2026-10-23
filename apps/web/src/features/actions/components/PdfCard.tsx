import type { PdfDocFields } from '../types';

// Persisted outlines are drafts. Only backend tool results provide file downloads.
export function PdfCard({ data }: { data: PdfDocFields; onCommit?: (updated: PdfDocFields) => void; compact?: boolean }) {
  return <div role="status">
    <strong>{data.title || 'Document draft'}</strong>
    <p>This is a draft outline. Submit your document request in chat to generate and validate a downloadable file.</p>
    <ul>{data.outline.map((item, index) => <li key={index}>{item}</li>)}</ul>
  </div>;
}

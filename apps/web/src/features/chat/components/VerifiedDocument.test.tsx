import { render, screen, waitFor, cleanup } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { VerifiedDocument } from './VerifiedDocument';

afterEach(() => { cleanup(); vi.restoreAllMocks(); });
const bytes = new TextEncoder().encode('%PDF-1.7 test');
async function record() {
  const hash = await crypto.subtle.digest('SHA-256', bytes);
  return { validationStatus: 'validated', fileSizeBytes: bytes.length,
    sha256: Array.from(new Uint8Array(hash), b => b.toString(16).padStart(2, '0')).join(''),
    downloadUrl: '/api/v1/generated-docs/test' };
}

it('shows completion only after validated bytes can be downloaded', async () => {
  const data = await record();
  let resolve!: (value: Response) => void;
  vi.spyOn(globalThis, 'fetch').mockImplementation(() => new Promise(r => { resolve = r; }));
  render(<VerifiedDocument data={data}><a href={data.downloadUrl}>Download PDF</a></VerifiedDocument>);
  expect(screen.queryByRole('link')).toBeNull();
  expect(screen.getByRole('status')).toBeInTheDocument();
  resolve(new Response(bytes));
  await waitFor(() => expect(screen.getByRole('link')).toBeInTheDocument());
});

it.each(['missing-validation', 'http-error', 'bad-bytes', 'network-error'])('fails closed: %s', async failure => {
  const data = await record();
  if (failure === 'missing-validation') data.validationStatus = 'pending';
  vi.spyOn(globalThis, 'fetch').mockImplementation(async () => {
    if (failure === 'network-error') throw new Error('offline');
    return failure === 'http-error' ? new Response('', { status: 404 }) : new Response('wrong');
  });
  render(<VerifiedDocument data={data}>Completed</VerifiedDocument>);
  await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument());
  expect(screen.queryByText('Completed')).toBeNull();
});

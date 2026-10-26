import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { VRMAvatar } from './VRMAvatar';

vi.mock('@react-three/fiber', () => ({
  Canvas: () => <div data-testid="webgl-canvas" />,
  useFrame: vi.fn(), useThree: vi.fn(),
}));
vi.mock('./ProceduralAvatar', () => ({ ProceduralAvatar: () => <div data-testid="fallback-avatar" /> }));
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it('keeps hook order stable when moving between fallback, VRM, and text modes', async () => {
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({ getExtension: () => null } as any);
  const props = { companionId: 'hinaa' as const, state: 'idle' as const, reducedMotion: false, textOnly: false };
  const { rerender } = render(<VRMAvatar {...props} modelUrl={null} />);
  await waitFor(() => expect(screen.getByTestId('fallback-avatar')).toBeInTheDocument());
  rerender(<VRMAvatar {...props} modelUrl="/models/test.vrm" />);
  await waitFor(() => expect(screen.getByTestId('webgl-canvas')).toBeInTheDocument());
  rerender(<VRMAvatar {...props} modelUrl="/models/test.vrm" textOnly />);
  expect(screen.queryByTestId('webgl-canvas')).toBeNull();
  rerender(<VRMAvatar {...props} modelUrl="/models/test.vrm" />);
  await waitFor(() => expect(screen.getByTestId('webgl-canvas')).toBeInTheDocument());
});

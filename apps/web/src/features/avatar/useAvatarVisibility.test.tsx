import { act, cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { useAvatarVisibility } from './useAvatarVisibility';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

it('pauses offscreen and hidden avatars and resumes visible avatars', () => {
  let callback!: IntersectionObserverCallback;
  const disconnect = vi.fn();
  vi.stubGlobal('IntersectionObserver', class {
    constructor(cb: IntersectionObserverCallback) { callback = cb; }
    observe() {}
    disconnect = disconnect;
  });
  function Probe() { const { ref, visible } = useAvatarVisibility(); return <div ref={ref} data-testid="stage">{String(visible)}</div>; }
  const { unmount } = render(<Probe />);
  expect(screen.getByTestId('stage')).toHaveTextContent('true');
  act(() => callback([{ isIntersecting: false }] as IntersectionObserverEntry[], {} as IntersectionObserver));
  expect(screen.getByTestId('stage')).toHaveTextContent('false');
  act(() => callback([{ isIntersecting: true }] as IntersectionObserverEntry[], {} as IntersectionObserver));
  expect(screen.getByTestId('stage')).toHaveTextContent('true');
  vi.spyOn(document, 'hidden', 'get').mockReturnValue(true);
  act(() => document.dispatchEvent(new Event('visibilitychange')));
  expect(screen.getByTestId('stage')).toHaveTextContent('false');
  unmount();
  expect(disconnect).toHaveBeenCalled();
});

import { useEffect, useState } from 'react';

/** Pause WebGL work when the canvas cannot be seen. */
export function useAvatarVisibility() {
  const [element, ref] = useState<HTMLDivElement | null>(null);
  const [visible, setVisible] = useState(() => !document.hidden);
  useEffect(() => {
    let intersecting = true;
    const update = () => setVisible(intersecting && !document.hidden);
    const observer = typeof IntersectionObserver === 'undefined' ? null : new IntersectionObserver(entries => {
      intersecting = entries[0]?.isIntersecting ?? true;
      update();
    });
    if (element) observer?.observe(element);
    document.addEventListener('visibilitychange', update);
    update();
    return () => { observer?.disconnect(); document.removeEventListener('visibilitychange', update); };
  }, [element]);
  return { ref, visible };
}

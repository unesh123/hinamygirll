import { lazy, Suspense, type ComponentProps } from 'react';
import type { AvatarPresence as Presence } from '../../components/ui/AvatarPresence';

const PresenceCanvas = lazy(() => import('../../components/ui/AvatarPresence').then(module => ({ default: module.AvatarPresence })));

export function LazyAvatarPresence(props: ComponentProps<typeof Presence>) {
  return <Suspense fallback={<div role="status">Loading companion…</div>}><PresenceCanvas {...props} /></Suspense>;
}

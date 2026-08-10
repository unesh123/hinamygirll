/**
 * useProviderRouting.ts
 *
 * Bridges the user's settings with the runtime provider health to determine
 * the active provider for the next chat turn.
 */
import { useMemo } from "react";
import type { ProvidersState } from "../types/provider";
import type { ProviderPreferences } from "../../settings/types/settings";
import { resolveProviderSelection, type ProviderRuntimeSelection } from "../utils/resolveProviderSelection";

export function useProviderRouting(
  settings: ProviderPreferences,
  providers: ProvidersState
): ProviderRuntimeSelection {
  return useMemo(() => {
    return resolveProviderSelection(settings, providers);
  }, [settings, providers]);
}

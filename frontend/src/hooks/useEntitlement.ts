import { useQuery } from "@tanstack/react-query"
import { getMyEntitlements } from "@/lib/api"
import type { Entitlement } from "@/lib/types"

export const ENTITLEMENT_QUERY_KEY = ["entitlement", "me"] as const

export function useEntitlement() {
  return useQuery<Entitlement>({
    queryKey: ENTITLEMENT_QUERY_KEY,
    queryFn: getMyEntitlements,
    staleTime: 60_000,      // 1 min — license status doesn't change per-second
    refetchOnWindowFocus: true,
  })
}

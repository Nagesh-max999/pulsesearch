"use client";

import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "./api";

/**
 * Subscribes to the real, per-user activity stream over SSE (document status
 * transitions and searches — see backend app/api/routes/events.py) and
 * invalidates the affected React Query caches as they happen, so aggregate
 * numbers like the dashboard's document/search counts update live instead of
 * only on the next page load or explicit refetch. No polling involved.
 */
export function useUserEvents(userId: string | null) {
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!userId) return;

    function invalidateDocuments() {
      queryClient.invalidateQueries({ queryKey: ["documents"] });
      queryClient.invalidateQueries({ queryKey: ["document-analytics"] });
    }

    function invalidateSearch() {
      queryClient.invalidateQueries({ queryKey: ["search-analytics"] });
    }

    const source = new EventSource(api.userEventsUrl());

    // Redis pub/sub has no replay: an event published before this connection
    // finishes its handshake is simply gone. Background processing can finish
    // in well under a second once models are warm, so that window is real —
    // syncing once on open catches up on anything that happened between the
    // page's initial fetch and the stream actually going live, after which
    // live events alone keep things current.
    source.onopen = () => {
      invalidateDocuments();
      invalidateSearch();
    };

    source.addEventListener("document_status", invalidateDocuments);
    source.addEventListener("search", invalidateSearch);

    source.onerror = () => {
      // EventSource retries the connection on its own; nothing to do here
      // beyond letting it — closing would prevent that automatic recovery.
      // The onopen handler above re-syncs once the retry succeeds, so a
      // dropped connection doesn't leave the dashboard stale either.
    };

    return () => source.close();
  }, [userId, queryClient]);
}

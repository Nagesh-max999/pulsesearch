"use client";

import { useEffect, useState } from "react";
import { api } from "./api";
import type { DocumentStatus } from "./types";

const TERMINAL: DocumentStatus[] = ["COMPLETED", "FAILED"];

/**
 * Subscribes to real backend processing-status events over SSE for one document.
 * No polling or client-side timers are involved — the stream closes itself once
 * the backend reports a terminal status.
 */
export function useDocumentStatus(documentId: string, initialStatus: DocumentStatus) {
  const [status, setStatus] = useState<DocumentStatus>(initialStatus);

  useEffect(() => {
    if (TERMINAL.includes(initialStatus)) return;

    const source = new EventSource(api.documentEventsUrl(documentId));
    source.addEventListener("status", (event: MessageEvent) => {
      const next = event.data as DocumentStatus;
      setStatus(next);
      if (TERMINAL.includes(next)) source.close();
    });
    source.onerror = () => source.close();

    return () => source.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [documentId]);

  return status;
}

import { useState, useEffect } from "react";
import { getHealth } from "../api/client";

// Polls the backend so the UI can tell three states apart: the server is
// unreachable, the server is up but MySQL is not, and everything is fine.
export function useBackendHealth(intervalMs = 15000) {
  const [state, setState] = useState({ status: "checking", database: null });

  useEffect(() => {
    const controller = new AbortController();
    let timer = null;
    let cancelled = false;

    const check = async () => {
      try {
        const data = await getHealth(controller.signal);
        if (!cancelled) setState({ status: data.status, database: data.database });
      } catch (err) {
        if (err.name === "AbortError" || cancelled) return;
        setState({ status: "offline", database: null });
      }
      // Scheduled after the response rather than on a fixed interval, so a
      // slow reply can never stack requests on top of each other.
      if (!cancelled) timer = setTimeout(check, intervalMs);
    };

    check();
    return () => {
      cancelled = true;
      controller.abort();
      clearTimeout(timer);
    };
  }, [intervalMs]);

  return state;
}

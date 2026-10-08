import { useCallback, useEffect, useState } from "react";
import { api } from "../services/api";
import type { SalesFilters, SalesResponse } from "../types/api";

export function useSales() {
  const [filters, setFilters] = useState<SalesFilters>({});
  const [revision, setRevision] = useState(0);
  const [data, setData] = useState<SalesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const refresh = useCallback(() => setRevision((value) => value + 1), []);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setData(null);
    setError("");
    api
      .sales(filters, controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) setData(result);
      })
      .catch((failure: unknown) => {
        if (!controller.signal.aborted)
          setError(
            failure instanceof Error
              ? failure.message
              : "Unable to load sales.",
          );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [filters, revision]);
  return { data, loading, error, filters, setFilters, refresh };
}

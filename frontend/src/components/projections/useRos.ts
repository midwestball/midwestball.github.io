"use client";

import { useEffect, useState } from "react";
import { loadRosSnapshot } from "@/lib/projections";
import type { RosSnapshot } from "@/lib/ros";

export function useRos() {
  const [snapshot, setSnapshot] = useState<RosSnapshot | null>(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    loadRosSnapshot(controller.signal).then(data => {
      if (!controller.signal.aborted) setSnapshot(data);
    }).catch(cause => {
      if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "Could not load ROS projections.");
    });
    return () => controller.abort();
  }, [attempt]);
  return { snapshot, error, retry: () => { setError(""); setSnapshot(null); setAttempt(n => n + 1); } };
}

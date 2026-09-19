"use client";

import { useEffect } from "react";

/** Legacy path — Compare now lives at `/compare`. */
export default function LegacyFfoptimRedirect() {
  useEffect(() => {
    const qs = window.location.search;
    window.location.replace(qs ? `/compare/${qs}` : "/compare/");
  }, []);

  return (
    <p className="px-4 py-8 text-sm text-zinc-500">Redirecting to Compare…</p>
  );
}

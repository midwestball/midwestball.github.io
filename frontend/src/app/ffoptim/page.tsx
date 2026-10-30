"use client";
import { useEffect } from "react";
export default function LegacySearchRedirect() {
  useEffect(() => { window.location.replace(`/search/${window.location.search}${window.location.hash}`); }, []);
  return <main className="p-4 text-sm text-muted-foreground">Opening Search...</main>;
}

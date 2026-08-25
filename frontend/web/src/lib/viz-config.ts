/**
 * Public Supabase Storage prefix for Ballnet JSON, e.g.
 * https://<ref>.supabase.co/storage/v1/object/public/knowball-public
 *
 * Knowball only fetches public objects — no Supabase client / service key.
 */
export function vizPreferLocal(): boolean {
  const flag = process.env.VIZ_PREFER_LOCAL?.trim().toLowerCase();
  if (flag === "1" || flag === "true" || flag === "yes") return true;
  return Boolean(process.env.BALLNET_DATA_DIR?.trim());
}

function supabaseProjectUrl(): string | null {
  const candidates = [
    process.env.VIZ_STORAGE_BASE_URL,
    process.env.NEXT_PUBLIC_SUPABASE_URL,
    process.env.SUPABASE_URL,
    process.env.supabase_url,
  ];
  for (const raw of candidates) {
    const url = raw?.trim().replace(/\/$/, "");
    if (!url) continue;
    // Full storage prefix passed explicitly.
    if (url.includes("/storage/v1/object/public/")) return url;
    return `${url}/storage/v1/object/public/knowball-public`;
  }
  return null;
}

/** Remote Storage base, or null when local-only mode is active. */
export function vizStorageBase(): string | null {
  if (vizPreferLocal()) return null;
  return supabaseProjectUrl();
}

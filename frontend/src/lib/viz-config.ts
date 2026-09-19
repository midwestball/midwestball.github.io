/**
 * Public Supabase Storage prefix for Ballnet JSON, e.g.
 * https://<ref>.supabase.co/storage/v1/object/public/knowball-public
 *
 * Knowball only fetches public objects — no Supabase client / service key.
 * Local and prod both read Storage (`docs/adr/2026-09-18-storage-only-loader.md`).
 */

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

/** Remote Storage base. Null when the Storage env is unset. */
export function vizStorageBase(): string | null {
  return supabaseProjectUrl();
}

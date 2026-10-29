/** Resolve one immutable Ballnet revision per page load; projections use their own root. */
export function createDatasetBaseResolver(root: string, fetcher: typeof fetch = fetch) {
  let resolved: Promise<string | null> | null = null;
  return async (): Promise<string | null> => {
    if (!resolved) {
      resolved = (async () => {
        try {
          const response = await fetcher(`${root}/index/ballnet-dataset.json`, { cache: "no-store" });
          if (response.status === 404) return root; // Existing installations before migration.
          if (response.status === 400) {
            const error: unknown = await response.json();
            if (error && typeof error === "object" && "code" in error && error.code === "NoSuchKey") return root;
            return null;
          }
          if (!response.ok) return null;
          const value: unknown = await response.json();
          if (!value || typeof value !== "object" || !("schemaVersion" in value) || value.schemaVersion !== 1 || !("prefix" in value) || typeof value.prefix !== "string") return null;
          if (value.prefix === "") return root; // Explicit rollback to the legacy dataset.
          if (!/^migrations\/[a-z0-9-]+$/.test(value.prefix)) return null;
          return `${root}/${value.prefix}`;
        } catch {
          return null;
        }
      })();
    }
    const base = await resolved;
    if (base == null) resolved = null; // Transient or malformed pointer: retry on the next request.
    return base;
  };
}

const resolvers = new Map<string, ReturnType<typeof createDatasetBaseResolver>>();

export function ballnetDatasetBase(root: string): Promise<string | null> {
  let resolver = resolvers.get(root);
  if (!resolver) {
    resolver = createDatasetBaseResolver(root);
    resolvers.set(root, resolver);
  }
  return resolver();
}

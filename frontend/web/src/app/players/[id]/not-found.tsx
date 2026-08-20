export default function NotFound() {
  return (
    <main className="mx-auto max-w-3xl px-4 py-8">
      <p className="text-xs font-semibold tracking-[0.2em] text-zinc-500 uppercase">
        404
      </p>
      <h1 className="mt-1 text-3xl font-semibold tracking-tight">
        Player not found
      </h1>
      <p className="mt-2 text-sm text-zinc-600">
        That id is not in the skeleton roster.
      </p>
    </main>
  );
}

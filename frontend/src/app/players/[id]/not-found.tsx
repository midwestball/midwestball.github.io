import Link from "next/link";
export default function NotFound() {
  return <main className="mx-auto max-w-6xl p-4"><h1 className="text-3xl font-semibold">Player link unavailable</h1>
    <Link href="/search/" className="underline">Open player comparison</Link>
  </main>;
}

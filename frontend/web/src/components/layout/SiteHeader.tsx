import Link from "next/link";

const NAV = [
  { href: "/", label: "Home" },
  { href: "/search", label: "Search" },
  { href: "/ballnet", label: "Projections" },
  { href: "/ffoptim", label: "Compare" },
] as const;

export function SiteHeader() {
  return (
    <header className="border-b border-zinc-200 bg-white">
      <div className="mx-auto flex max-w-3xl items-center justify-between gap-3 px-4 py-2.5">
        <Link href="/" className="min-w-0">
          <p className="text-xs font-semibold tracking-[0.2em] text-zinc-500 uppercase">
            Knowball
          </p>
          <p className="text-sm font-semibold tracking-tight text-zinc-900">
            Player stats
          </p>
        </Link>
        <nav className="flex items-center gap-1 text-sm">
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="rounded-none px-2 py-1 text-zinc-600 hover:bg-zinc-50 hover:text-zinc-900"
            >
              {item.label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}

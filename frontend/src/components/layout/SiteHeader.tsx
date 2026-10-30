import Link from "next/link";

const NAV = [
  { href: "/", label: "Home" },
  { href: "/search", label: "Search" },
  { href: "/ballnet", label: "Projections" },
  { href: "/trades", label: "Trades" },
] as const;

export function SiteHeader() {
  return (
    <header className="border-b border-border bg-card">
      <div className="mx-auto flex max-w-3xl flex-wrap items-center justify-between gap-3 px-4 py-2.5">
        <Link href="/" className="min-w-0">
          <p className="text-xs font-semibold tracking-[0.2em] text-muted-foreground uppercase">
            midwestball
          </p>
          <p className="text-sm font-semibold tracking-tight text-foreground">
            Player stats
          </p>
        </Link>
        <nav className="flex max-w-full items-center gap-1 overflow-x-auto text-sm">
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="rounded-none px-2 py-1 text-text-secondary hover:bg-muted hover:text-foreground"
            >
              {item.label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}

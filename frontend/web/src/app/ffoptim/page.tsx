import { redirect } from "next/navigation";

/** Legacy path — Compare now lives at `/compare`. */
export default async function LegacyFfoptimRedirect({
  searchParams,
}: {
  searchParams: Promise<{ p?: string; season?: string }>;
}) {
  const { p, season } = await searchParams;
  const params = new URLSearchParams();
  if (p) params.set("p", p);
  if (season) params.set("season", season);
  const qs = params.toString();
  redirect(qs ? `/compare?${qs}` : "/compare");
}

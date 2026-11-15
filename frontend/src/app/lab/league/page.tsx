import type { Metadata } from "next";
import { LeagueLabClient } from "./LeagueLabClient";

export const metadata: Metadata = {
  title: "League lab · midwestball",
  description: "Link a Sleeper or ESPN league and estimate rest-of-season points.",
};

export default function LeagueLabPage() {
  return <LeagueLabClient />;
}

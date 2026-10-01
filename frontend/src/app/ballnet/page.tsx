import { Suspense } from "react";

import { ProjectionsPageClient } from "@/components/projections/ProjectionsPageClient";

export default function ProjectionsPage() {
  return (
    <Suspense
      fallback={
        <div className="px-4 py-8 text-sm text-zinc-500">
          Loading projections…
        </div>
      }
    >
      <ProjectionsPageClient />
    </Suspense>
  );
}

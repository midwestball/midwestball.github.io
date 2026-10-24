import { Suspense } from "react";

import { ProjectionHorizons } from "@/components/projections/ProjectionHorizons";

export default function ProjectionsPage() {
  return (
    <Suspense
      fallback={
        <div className="px-4 py-8 text-sm text-zinc-500">
          Loading projections…
        </div>
      }
    >
      <ProjectionHorizons />
    </Suspense>
  );
}

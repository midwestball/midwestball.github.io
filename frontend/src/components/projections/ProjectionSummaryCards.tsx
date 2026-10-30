"use client";
import type { ProjectionEntitySummary } from "@/lib/projections";
import { PlayerComparisonLink } from "@/components/PlayerComparisonLink";
import { TeamAbbr } from "@/components/TeamAbbr";
import { assignTeamLineColors } from "@/lib/team-colors";
const STYLES=[{color:"#0072B2",dash:""},{color:"#D55E00",dash:"8 3"},{color:"#009E73",dash:"3 3"},{color:"#CC79A7",dash:"10 3 2 3"}];
export const projectionStyle=(i:number)=>STYLES[i%STYLES.length]!;
export function ProjectionSummaryCards({entities,focus,onFocus,onRemove,season}:{entities:ProjectionEntitySummary[];focus:string|null;onFocus:(id:string)=>void;onRemove:(id:string)=>void;season?:number}) {
  const colors=assignTeamLineColors(entities);
  return <ul className="grid gap-2 sm:grid-cols-2" aria-label="Selected projections">{entities.map((e,i)=><li key={e.entityKey} className={`border bg-card p-3 ${focus===e.entityKey?"border-ring":"border-border"}`}>
    <div><span className="inline-block h-1 w-8 align-middle" style={{background:colors.get(e.entityKey)??projectionStyle(i).color}}/> <strong>{e.playerId ? <PlayerComparisonLink playerId={e.playerId} season={season}>{e.name}</PlayerComparisonLink> : e.name}</strong> <span aria-hidden className="inline-flex align-middle"><TeamAbbr team={e.team} className="[&>span:last-child]:hidden" /></span></div>
    <button type="button" className="mt-1 w-full text-left" aria-label={`Focus projection for ${e.name}`} onClick={()=>onFocus(e.entityKey)} aria-pressed={focus===e.entityKey}>
      <span className="text-xs text-muted-foreground">{e.position} · {e.team} vs {e.opponent}</span>
      <span className="mt-1 block text-sm">{e.expectedPoints.toFixed(1)} expected points{e.availability ? ` · ${e.availability}` : ""}</span>
    </button>
    <button type="button" onClick={()=>onRemove(e.entityKey)} className="mt-2 border border-border px-2 py-1 text-xs font-semibold text-text-secondary transition-colors hover:border-ring hover:bg-muted hover:text-foreground focus:border-ring focus:bg-muted focus:text-foreground focus:outline-2 focus:outline-offset-2 focus:outline-ring" aria-label={`Remove ${e.name}`}>Remove</button>
  </li>)}</ul>;
}

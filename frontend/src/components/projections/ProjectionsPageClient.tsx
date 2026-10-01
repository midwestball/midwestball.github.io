"use client";
import { useCallback,useEffect,useMemo,useRef,useState } from "react";
import { useSearchParams } from "next/navigation";
import { loadProjectionEntity,loadProjectionManifest,loadProjectionSnapshot,parseProjectionSelection,ProjectionLoadError,type ProjectionEntityDistribution,type ProjectionIndex,type ProjectionPointer,type ProjectionManifest } from "@/lib/projections";
import { canCompare,probabilityAtLeast,resolveThreshold,type ThresholdQuery } from "@/lib/projection-math";
import { ProjectionPicker } from "./ProjectionPicker";
import { ProjectionSummaryCards } from "./ProjectionSummaryCards";
import { ProjectionOverlayChart,THRESHOLD_COLOR } from "./ProjectionOverlayChart";
import { assignTeamLineColors,readableTextOn } from "@/lib/team-colors";
import { ProjectionPointsInput } from "./ProjectionPointsInput";

type Snapshot={pointer:ProjectionPointer;index:ProjectionIndex};
export function ProjectionsPageClient(){const searchParams=useSearchParams();const [snapshot,setSnapshot]=useState<Snapshot|null>(null);const [status,setStatus]=useState<"loading"|"ready"|"unavailable"|"network"|"invalid">("loading");const [message,setMessage]=useState("");const [curveError,setCurveError]=useState("");const [selected,setSelected]=useState<string[]>([]);const [focus,setFocus]=useState<string|null>(null);const [stale,setStale]=useState(0);const [curves,setCurves]=useState(new Map<string,ProjectionEntityDistribution>());const [query,setQuery]=useState<ThresholdQuery>({source:"probability",value:.5});const [manifest,setManifest]=useState<ProjectionManifest|null>(null);const [revision,setRevision]=useState(0);const curveRun=useRef(0);
 // The snapshot depends only on the retry counter. Selection is hydrated from the URL
 // once, here, and every later edit writes state first and the URL second. Deriving
 // state from the URL on every change used to abort the request the new selection had
 // just started, which surfaced as a spurious "Could not reach projection storage." page.
 useEffect(()=>{
  const ctl=new AbortController();
  const initialUrl=new URLSearchParams(searchParams.toString());
  loadProjectionSnapshot(ctl.signal).then(s=>{
   if(ctl.signal.aborted)return;
   const parsed=parseProjectionSelection(initialUrl.toString(),new Set(s.index.entities.map(e=>e.entityKey)));
   setSnapshot(s);setSelected(parsed.selected);setFocus(parsed.focus);setStale(parsed.stale);setStatus("ready");
  }).catch(e=>{
   if(ctl.signal.aborted)return;
   if(e instanceof Error&&e.name==="AbortError")return;
   setStatus(e instanceof ProjectionLoadError?e.kind:"network");
   setMessage(e instanceof Error?e.message:"Could not load projections.");
  });
  return()=>ctl.abort();
  // eslint-disable-next-line react-hooks/exhaustive-deps
 },[revision]);
 const updateUrl=useCallback((ids:string[],focused:string|null)=>{const p=new URLSearchParams();if(ids.length)p.set("p",ids.join(","));if(focused)p.set("focus",focused);history.replaceState(null,"",`${location.pathname}${p.size?`?${p}`:""}`)},[]);
  useEffect(()=>{
  const run=++curveRun.current;
  if(!snapshot||selected.length===0)return;
  const ctl=new AbortController();
  Promise.all(selected.map(id=>{const summary=snapshot.index.entities.find(e=>e.entityKey===id)!;return loadProjectionEntity(snapshot.pointer.indexPath,snapshot.index,summary,ctl.signal)})).then(rows=>{if(run===curveRun.current&&!ctl.signal.aborted){setCurves(new Map(rows.map(r=>[r.entityKey,r])));setCurveError("")}}).catch(e=>{
   if(run!==curveRun.current||ctl.signal.aborted)return;
   // An abort is never a user-facing failure. If one reaches us the next effect run
   // will replace it, so stay quiet rather than flashing a red banner.
   if(e instanceof Error&&e.name==="AbortError")return;
   setCurveError(e instanceof Error?e.message:"Could not load selected projections.");
  });return()=>ctl.abort()},[snapshot,selected]);
 const entities=useMemo(()=>selected.map(id=>snapshot?.index.entities.find(e=>e.entityKey===id)).filter((e):e is NonNullable<typeof e>=>!!e),[snapshot,selected]);const focusedCurve=focus?curves.get(focus):undefined;const lineColors=useMemo(()=>assignTeamLineColors(entities),[entities]);const resolved=snapshot&&focusedCurve?resolveThreshold(snapshot.index.xGrid,focusedCurve,query):null;
 const add=(id:string)=>{if(selected.includes(id)||selected.length>=4)return;
  // Only compare inside a fantasy-relevant group: QB vs QB, RB/WR/TE together, K vs K, DST vs DST.
  const incoming=snapshot?.index.entities.find(e=>e.entityKey===id);
  const current=entities;
  if(incoming&&current.some(e=>!canCompare(e.position,incoming.position)))return;
  const ids=[...selected,id];setCurveError("");setSelected(ids);const nextFocus=focus??id;setFocus(nextFocus);updateUrl(ids,nextFocus)};const remove=(id:string)=>{setCurveError("");const ids=selected.filter(x=>x!==id);const nextFocus=focus===id?(ids[0]??null):focus;setSelected(ids);setFocus(nextFocus);updateUrl(ids,nextFocus)};const chooseFocus=(id:string)=>{setFocus(id);updateUrl(selected,id)};
 if(status==="loading")return <State text="Loading current projection snapshot…"/>;if(status!=="ready"||!snapshot)return <State text={message||"Projections are unavailable."} action={()=>{setStatus("loading");setMessage("");setStatus("loading");setRevision(x=>x+1)}}/>;
const generated=new Date(snapshot.index.generatedAt);return <div><header className="border-b border-zinc-200 bg-white"><div className="mx-auto max-w-5xl px-4 py-5"><p className="text-xs font-semibold tracking-[0.2em] text-zinc-500 uppercase">Upcoming week · {snapshot.index.season} week {snapshot.index.week}</p><h1 className="mt-0.5 text-3xl font-semibold tracking-tight">Projections</h1><p className="mt-1 max-w-2xl text-sm text-zinc-600">Compare estimated fantasy-point distributions. Updated <time dateTime={snapshot.index.generatedAt}>{Number.isNaN(generated.valueOf())?snapshot.index.generatedAt:generated.toLocaleString()}</time>.</p></div></header><main className="mx-auto max-w-5xl space-y-4 px-4 py-4">{stale>0&&<p role="status" className="border border-amber-300 bg-amber-50 p-3 text-sm">{stale} shared selection{stale===1?" was":"s were"} unavailable in this snapshot.</p>}<ProjectionPicker entities={snapshot.index.entities} selected={selected} onAdd={add}/>{entities.length===0?<div className="border border-zinc-200 bg-white p-5 text-sm text-zinc-600">Search above to select up to four players or defenses.</div>:<><ProjectionSummaryCards entities={entities} focus={focus} onFocus={chooseFocus} onRemove={remove}/>{curveError&&<p role="alert" className="border border-red-300 bg-red-50 p-3 text-sm text-red-800">{curveError}</p>}{focusedCurve&&resolved?<><ProjectionOverlayChart grid={snapshot.index.xGrid} entities={entities} curves={curves} focus={focus} threshold={resolved.points} onFocus={chooseFocus} onThresholdChange={points=>setQuery({source:"points",value:points})}/><ProjectionPointsInput points={resolved.points} min={focusedCurve.lowerBound??snapshot.index.xGrid[0]!} max={snapshot.index.xGrid.at(-1)!} onCommit={points=>setQuery({source:"points",value:points})}/><table className="w-full border-collapse bg-white text-left text-sm"><caption className="sr-only">Selected projection values</caption><thead><tr>{["Player","Matchup","Expected points",`Chance of scoring ${resolved.points.toFixed(1)} or more`,"Median points (50th percentile)"].map(h=><th key={h} scope="col" className="border border-zinc-200 p-2">{h}</th>)}</tr></thead><tbody>{entities.map(e=>{const c=curves.get(e.entityKey);const color=lineColors.get(e.entityKey)??THRESHOLD_COLOR;if(!c)return <tr key={e.entityKey}><th scope="row" className="border border-zinc-200 p-2">{e.name} ({e.position})</th><td className="border border-zinc-200 p-2">{e.team} vs {e.opponent}</td><td className="border border-zinc-200 p-2 tabular-nums">{e.expectedPoints.toFixed(1)}</td><td className="border border-zinc-200 p-2">Loading…</td><td className="border border-zinc-200 p-2">Loading…</td></tr>;const chance=probabilityAtLeast(snapshot.index.xGrid,c,resolved.points);const median=resolveThreshold(snapshot.index.xGrid,c,{source:"probability",value:.5});return <tr key={e.entityKey} className={focus===e.entityKey?"bg-zinc-50":undefined}><th scope="row" className="border border-zinc-200 p-2"><span className="mr-1.5 inline-block h-2.5 w-2.5 align-middle" style={{backgroundColor:color}} />{e.name} ({e.position})</th><td className="border border-zinc-200 p-2">{e.team} vs {e.opponent}</td><td className="border border-zinc-200 p-2 tabular-nums">{e.expectedPoints.toFixed(1)}</td><td className="border border-zinc-200 p-2"><span className="rounded-none px-1 py-0.5 font-semibold tabular-nums" style={{backgroundColor:color,color:readableTextOn(color)}}>{(chance*100).toFixed(1)}%</span></td><td className="border border-zinc-200 p-2 tabular-nums">{median.points.toFixed(1)}</td></tr>})}</tbody></table></>:<State text="Loading selected distributions…"/>}</>}<details className="border border-zinc-200 bg-white p-3 text-sm"><summary className="cursor-pointer font-semibold">Scoring and methodology</summary><p className="mt-2">{snapshot.index.scoringProfile}. Expected fantasy points are the model-draw mean. Probabilities are estimated from a smoothed, finite-grid KDE. This fixed scoring profile may not match every fantasy platform.</p><ul className="mt-2 list-disc pl-5">{Object.entries(snapshot.index.scoringDescriptions).map(([pos,desc])=><li key={pos}><strong>{pos}:</strong> {desc} <span className="text-zinc-500">({snapshot.index.positionModelStatus[pos as keyof typeof snapshot.index.positionModelStatus].replaceAll("_"," ")})</span></li>)}</ul><button className="mt-3 text-sm font-semibold underline" onClick={()=>loadProjectionManifest(snapshot.pointer.indexPath,snapshot.index).then(setManifest).catch(e=>setMessage(e instanceof Error?e.message:"Manifest unavailable"))}>Load provenance</button>{manifest&&<pre className="mt-2 max-h-64 overflow-auto bg-zinc-50 p-2 text-xs">{JSON.stringify(manifest,null,2)}</pre>}</details></main></div>}
function State({text,action}:{text:string;action?:()=>void}){return <main className="mx-auto max-w-3xl px-4 py-8"><div role="status" className="border border-zinc-200 bg-white p-4 text-sm text-zinc-600">{text}{action&&<button onClick={action} className="ml-3 font-semibold underline">Retry</button>}</div></main>}
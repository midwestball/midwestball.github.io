import { afterEach,describe,expect,it,vi } from "vitest";
import { loadProjectionEntity,loadProjectionSnapshot,NETWORK_ATTEMPTS,ProjectionLoadError } from "./projections";

const POINTER={schemaVersion:1 as const,season:2026,week:4,snapshotId:"snap",indexPath:"projections/2026/w4/snap/index.json",manifestPath:"projections/2026/w4/snap/manifest.json",generatedAt:"2026-09-30T00:00:00Z"};
const INDEX={schemaVersion:1 as const,season:2026,week:4,snapshotId:"snap",generatedAt:"2026-09-30T00:00:00Z",trainedThrough:{season:2026,week:3},modelFamily:"crps_forest",modelVersion:"v1",scoringProfile:"ppr-v1",scoringDescriptions:{QB:"a",RB:"a",WR:"a",TE:"a",K:"a",DST:"a"},positionModelStatus:{QB:"promoted",RB:"promoted",WR:"promoted",TE:"promoted",K:"initial_deployment",DST:"initial_deployment"},manifestPath:"manifest.json",xGrid:[0,1,2],entities:[]};
const ENTITY={schemaVersion:1 as const,snapshotId:"snap",entityKey:"e",expectedPoints:1,yMax:1,pdf:[0,1,0],cdf:[0,.5,1],lowerBound:null,bandwidth:1,nModelDraws:10000};
const SUMMARY={entityKey:"e",entityType:"player" as const,playerId:"p",name:"Example",position:"QB" as const,team:"CHI",opponent:"GB",expectedPoints:1,path:"entities/e.json"};
const jsonResponse=(v:unknown)=>new Response(JSON.stringify(v),{status:200,headers:{"content-type":"application/json"}});

vi.stubEnv("VIZ_STORAGE_BASE_URL","https://example.supabase.co/storage/v1/object/public/knowball-public");
afterEach(()=>{vi.unstubAllGlobals();});

describe("projection storage resilience",()=>{
 it("recovers from a single dropped connection instead of showing an error page",async()=>{
  let calls=0;
  vi.stubGlobal("fetch",vi.fn(async(url:string)=>{
   if(String(url).endsWith("current.json")){calls++;if(calls===1)throw new TypeError("Failed to fetch");return jsonResponse(POINTER);}
   return jsonResponse(INDEX);
  }));
  const result=await loadProjectionSnapshot();
  expect(result.pointer.snapshotId).toBe("snap");
  expect(calls).toBe(2);
 });

 it("gives up after the bounded number of attempts",async()=>{
  const fetchMock=vi.fn(async()=>{throw new TypeError("Failed to fetch");});
  vi.stubGlobal("fetch",fetchMock);
  await expect(loadProjectionSnapshot()).rejects.toBeInstanceOf(ProjectionLoadError);
  expect(fetchMock.mock.calls.length).toBe(NETWORK_ATTEMPTS);
 });

 it("does not retry a 404, which is a real missing snapshot",async()=>{
  const fetchMock=vi.fn(async()=>new Response("{}",{status:404}));
  vi.stubGlobal("fetch",fetchMock);
  await expect(loadProjectionSnapshot()).rejects.toMatchObject({kind:"unavailable"});
  expect(fetchMock.mock.calls.length).toBe(1);
 });

 it("does not report invalid JSON when the request is aborted mid-body",async()=>{
  const ctl=new AbortController();
  vi.stubGlobal("fetch",vi.fn(async()=>{
   ctl.abort();
   const err=new Error("The operation was aborted");err.name="AbortError";
   return Object.assign(jsonResponse(INDEX),{json:async()=>{throw err}});
  }));
  await expect(loadProjectionSnapshot(ctl.signal)).rejects.toMatchObject({name:"AbortError"});
 });

 it("a second caller with a healthy signal does not inherit the first caller's abort",async()=>{
  // React tears down the effect that started an entity fetch and immediately starts
  // another for the new selection. The second caller reuses the first caller's cached
  // request, so a request bound to the dead caller's signal surfaced as a live error.
  let release:()=>void=()=>{};
  const gate=new Promise<void>(r=>{release=r});
  let served=0;
  vi.stubGlobal("fetch",vi.fn(async()=>{served++;await gate;return jsonResponse(ENTITY);}));
  const index={xGrid:[0,1,2],snapshotId:"snap"} as never;

  const ctlA=new AbortController();
  const first=loadProjectionEntity(POINTER.indexPath,index,SUMMARY,ctlA.signal).catch(e=>e as Error);
  ctlA.abort();
  const second=loadProjectionEntity(POINTER.indexPath,index,SUMMARY,new AbortController().signal).catch(e=>e as Error);
  release();

  expect(await first).toMatchObject({name:"AbortError"});
  expect((await second as {entityKey?:string}).entityKey).toBe("e");
  expect(served).toBe(1);
 });

 it("a failed shared request is not left in the cache",async()=>{
  const index={xGrid:[0,1,2],snapshotId:"snap"} as never;
  // A distinct URL: an immutable object that already resolved stays cached on purpose.
  const other={...SUMMARY,entityKey:"e2",path:"entities/e2.json"};
  const otherEntity={...ENTITY,entityKey:"e2"};
  vi.stubGlobal("fetch",vi.fn(async()=>new Response("{}",{status:404})));
  await expect(loadProjectionEntity(POINTER.indexPath,index,other)).rejects.toMatchObject({kind:"unavailable"});
  vi.stubGlobal("fetch",vi.fn(async()=>jsonResponse(otherEntity)));
  const recovered=await loadProjectionEntity(POINTER.indexPath,index,other);
  expect(recovered.entityKey).toBe("e2");
 });
});

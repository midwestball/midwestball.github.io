import { describe,expect,it } from "vitest";
import { canCompare,pointsAtProbability,probabilityAtLeast,probabilityAtPoints,resolveThreshold } from "./projection-math";
import type { ProjectionEntityDistribution } from "./projections";
const curve:ProjectionEntityDistribution={schemaVersion:1,snapshotId:"s",entityKey:"e",expectedPoints:1,yMax:1,pdf:[0,1,0],cdf:[0,.5,1],lowerBound:null,bandwidth:1,nModelDraws:10000};
describe("projection math",()=>{it("integrates a partial trapezoid, not linear CDF",()=>expect(probabilityAtPoints([0,1,2],curve,.5)).toBeCloseTo(.125));it("inverts the quadratic",()=>{const x=pointsAtProbability([0,1,2],curve,.125);expect(x).toBeCloseTo(.5);expect(probabilityAtPoints([0,1,2],curve,x)).toBeCloseTo(.125)});it("maps endpoints",()=>{expect(pointsAtProbability([0,1,2],curve,0)).toBe(0);expect(pointsAtProbability([0,1,2],curve,1)).toBe(2)});it("uses the left edge of a plateau",()=>{const c={...curve,pdf:[1,0,0,1],cdf:[0,.5,.5,1]};expect(pointsAtProbability([0,1,2,3],c,.5)).toBe(1)});it("preserves the last-edited source",()=>expect(resolveThreshold([0,1,2],curve,{source:"points",value:.5}).points).toBeCloseTo(.5));
 it("reports the chance of scoring AT LEAST the threshold",()=>{const r=resolveThreshold([0,1,2],curve,{source:"points",value:.5});expect(r.atMost).toBeCloseTo(.125);expect(r.probability).toBeCloseTo(.875)});
 it("probabilityAtLeast is the complement of the CDF",()=>{for(const x of [0,.5,1,1.5,2]) expect(probabilityAtLeast([0,1,2],curve,x)).toBeCloseTo(1-probabilityAtPoints([0,1,2],curve,x))});
 it("inverts a typed probability through the CDF",()=>{const r=resolveThreshold([0,1,2],curve,{source:"probability",value:.875});expect(r.points).toBeCloseTo(.5);expect(r.probability).toBeCloseTo(.875)});
 it("a 50% chance is the median either way",()=>{const byPoints=resolveThreshold([0,1,2],curve,{source:"points",value:1});const byProb=resolveThreshold([0,1,2],curve,{source:"probability",value:.5});expect(byPoints.points).toBeCloseTo(1);expect(byProb.points).toBeCloseTo(1)});
 it("groups QB, skill, K, and DST separately",()=>{expect(canCompare("QB","QB")).toBe(true);expect(canCompare("RB","WR")).toBe(true);expect(canCompare("WR","TE")).toBe(true);expect(canCompare("RB","TE")).toBe(true);expect(canCompare("QB","RB")).toBe(false);expect(canCompare("K","QB")).toBe(false);expect(canCompare("DST","DST")).toBe(true);expect(canCompare("DST","K")).toBe(false)});});

/**
 * The comparison table labels its column "chance of scoring N or more", so it must
 * use the upper tail. The published CDF is the lower tail and reads as the mirror
 * image, which is an easy mistake to reintroduce.
 */
describe("upper-tail semantics for the comparison table",()=>{
  const grid=[0,1,2];
  it("uses the upper tail, not the CDF, for an \"or more\" figure",()=>{
    expect(probabilityAtLeast(grid,curve,.5)).toBeCloseTo(.875);
    expect(probabilityAtPoints(grid,curve,.5)).toBeCloseTo(.125);
  });
  it("falls as the bar rises, the way a chance of scoring more should",()=>{
    const values=[0,.5,1,1.5,2].map((x)=>probabilityAtLeast(grid,curve,x));
    for(let i=1;i<values.length;i+=1) expect(values[i]!).toBeLessThanOrEqual(values[i-1]!);
  });
  it("agrees with resolveThreshold for a points threshold",()=>{
    const resolved=resolveThreshold(grid,curve,{source:"points",value:.5});
    expect(probabilityAtLeast(grid,curve,resolved.points)).toBeCloseTo(resolved.probability);
  });
});

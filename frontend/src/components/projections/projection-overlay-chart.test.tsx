import React from "react";
import { act, cleanup, render,screen } from "@testing-library/react";
import { afterEach,describe,expect,it,vi } from "vitest";
import { ProjectionOverlayChart,THRESHOLD_COLOR,clampThreshold,snapThreshold,thresholdNudge,valueFromClientX,isOverThreshold } from "./ProjectionOverlayChart";
import type { ProjectionEntityDistribution,ProjectionEntitySummary } from "@/lib/projections";

afterEach(cleanup);
const grid=[0,1,2,3,4,5];
const curve=(key:string):ProjectionEntityDistribution=>({schemaVersion:1,snapshotId:"s",entityKey:key,expectedPoints:1,yMax:1,pdf:[0,.5,1,.5,0,0],cdf:[0,.1,.4,.8,1,1],lowerBound:null,bandwidth:1,nModelDraws:1000});
const ent=(key:string,team:string):ProjectionEntitySummary=>({entityKey:key,entityType:"player",playerId:key,name:key,position:"RB",team,opponent:"GB",expectedPoints:1,path:`entities/${key}.json`});

describe("threshold line rules",()=>{
 it("clamps to the published grid",()=>{
  expect(clampThreshold(-5,0,5)).toBe(0);
  expect(clampThreshold(99,0,5)).toBe(5);
  expect(clampThreshold(2.5,0,5)).toBe(2.5);
 });

 it("snaps a dragged value to one decimal place",()=>{
  expect(snapThreshold(2.4499,0,5)).toBe(2.4);
  expect(snapThreshold(2.46,0,5)).toBe(2.5);
  expect(snapThreshold(-3,0,5)).toBe(0);
  expect(snapThreshold(42,0,5)).toBe(5);
 });

 it("moves one point per arrow key and five with shift",()=>{
  expect(thresholdNudge("ArrowRight",3,false,0,5)).toBe(4);
  expect(thresholdNudge("ArrowLeft",3,false,0,5)).toBe(2);
  expect(thresholdNudge("ArrowRight",3,true,0,10)).toBe(8);
  expect(thresholdNudge("ArrowLeft",3,true,0,10)).toBe(0);
 });

 it("jumps to the grid ends and ignores other keys",()=>{
  expect(thresholdNudge("Home",3,false,0,5)).toBe(0);
  expect(thresholdNudge("End",3,false,0,5)).toBe(5);
  expect(thresholdNudge("a",3,false,0,5)).toBeNull();
  expect(thresholdNudge("Tab",3,false,0,5)).toBeNull();
 });
});

describe("threshold readout",()=>{
 // jsdom gives ResponsiveContainer a zero-sized box, so the SVG handle never mounts.
 // These cover the shell around it: the chart renders, and no tooltip is shown by default.
 it("renders no floating tooltip at all",()=>{
  render(<ProjectionOverlayChart grid={grid} entities={[ent("a","CHI")]} curves={new Map([["a",curve("a")]])} focus="a" threshold={3} onFocus={()=>{}} onThresholdChange={()=>{}}/>);
  expect(screen.queryByRole("status")).toBeNull();
  expect(screen.queryByRole("tooltip")).toBeNull();
  expect(screen.getByText(/Drag the vertical line/)).toBeTruthy();
 });

 // The chart measures its own plot box; jsdom reports zero, so stand in a 400px box.
 // Plot width is 400 - 44 (y axis) - 12 (right margin) = 344px across 0..5 points.
 const PLOT_LEFT=44, PLOT_RIGHT=12, WIDTH=400;
 const clientXFor=(value:number)=>PLOT_LEFT+(value/5)*(WIDTH-PLOT_LEFT-PLOT_RIGHT);
 // jsdom has no PointerEvent constructor, so dispatch a mouse event carrying the
 // pointer type name; React still routes it to the onPointer* handlers.
 const pointer=(target:Element|Window,type:string,clientX:number)=>{act(()=>{target.dispatchEvent(new MouseEvent(type,{bubbles:true,cancelable:true,clientX,button:0}));});};
 const mount=(onThresholdChange:(v:number)=>void)=>{
  const spy=vi.spyOn(Element.prototype,"getBoundingClientRect").mockReturnValue({left:0,top:0,width:WIDTH,height:288,right:WIDTH,bottom:288,x:0,y:0,toJSON:()=>({})} as DOMRect);
  const utils=render(<ProjectionOverlayChart grid={grid} entities={[ent("a","CHI")]} curves={new Map([["a",curve("a")]])} focus="a" threshold={3} onFocus={()=>{}} onThresholdChange={onThresholdChange}/>);
  const plot=screen.getByTestId("threshold-plot");
  return {...utils,plot,spy};
 };

 it("starts a drag when the pointer lands on the threshold line",()=>{
  const calls:number[]=[];
  const {plot,spy}=mount(v=>calls.push(v));
  pointer(plot,"pointerdown",clientXFor(3));
  pointer(window,"pointermove",clientXFor(4));
  pointer(window,"pointerup",clientXFor(4));
  expect(calls).toEqual([4]);
  spy.mockRestore();
 });

 it("ignores a press that lands well away from the threshold line",()=>{
  const calls:number[]=[];
  const {plot,spy}=mount(v=>calls.push(v));
  pointer(plot,"pointerdown",clientXFor(1));
  pointer(window,"pointermove",clientXFor(4));
  pointer(window,"pointerup",clientXFor(4));
  expect(calls).toEqual([]);
  spy.mockRestore();
 });

 it("commits exactly once across a whole drag, not per movement",()=>{
  const calls:number[]=[];
  const {plot,spy}=mount(v=>calls.push(v));
  pointer(plot,"pointerdown",clientXFor(3));
  pointer(window,"pointermove",clientXFor(3.4));
  pointer(window,"pointermove",clientXFor(3.8));
  pointer(window,"pointermove",clientXFor(4.2));
  expect(calls).toEqual([]);
  pointer(window,"pointerup",clientXFor(4.2));
  expect(calls).toEqual([4.2]);
  spy.mockRestore();
 });

 it("paints the threshold line in the colour the readout below uses",()=>{
  expect(THRESHOLD_COLOR).toMatch(/^#[0-9a-f]{6}$/i);
 });

 it("treats the cursor as on the line only inside the grab tolerance",()=>{
  // 344px across 0..5 points is 68.8px per point.
  const perUnit=344/5;
  expect(isOverThreshold(3,3,perUnit)).toBe(true);
  expect(isOverThreshold(3.15,3,perUnit)).toBe(true);
  expect(isOverThreshold(3.2,3,perUnit)).toBe(false);
  expect(isOverThreshold(1,3,perUnit)).toBe(false);
  // A collapsed plot has no pixels to judge against, so nothing is hovered.
  expect(isOverThreshold(3,3,0)).toBe(false);
  expect(isOverThreshold(null,3,perUnit)).toBe(false);
 });

 it("maps a cursor position to a threshold value across the measured plot box",()=>{
  // The left inset is the y axis, so x=0 is not at the edge of the container.
  expect(valueFromClientX(44,0,400,0,5)).toBeCloseTo(0,5);
  expect(valueFromClientX(44+344,0,400,0,5)).toBeCloseTo(5,5);
  expect(valueFromClientX(44+344/2,0,400,0,5)).toBeCloseTo(2.5,5);
  // Outside the plot the value clamps rather than running past the grid.
  expect(valueFromClientX(-200,0,400,0,5)).toBe(0);
  expect(valueFromClientX(9999,0,400,0,5)).toBe(5);
  expect(valueFromClientX(200,0,10,0,5)).toBeNull();
 });
});

import React from "react";
import { cleanup,fireEvent,render,screen } from "@testing-library/react";
import { afterEach,describe,expect,it,vi } from "vitest";
import { ProjectionPicker } from "./ProjectionPicker";
import { ProjectionPointsInput } from "./ProjectionPointsInput";
afterEach(cleanup);
const entity={entityKey:"e",entityType:"player" as const,playerId:"p",name:"Example",position:"QB" as const,team:"CHI",opponent:"GB",expectedPoints:20,path:"entities/e.json"};
describe("projection controls",()=>{it("disables additions at the four-entity cap",()=>{render(<ProjectionPicker entities={[entity]} selected={["a","b","c","d"]} onAdd={()=>{}}/>);expect(screen.getByLabelText("Add a projection").hasAttribute("disabled")).toBe(true)});it("commits the entered fantasy points on blur",()=>{const commit=vi.fn();render(<ProjectionPointsInput points={10} min={-5} max={50} onCommit={commit}/>);const input=screen.getByLabelText("Fantasy points threshold");fireEvent.change(input,{target:{value:"12.5"}});fireEvent.blur(input);expect(commit).toHaveBeenCalledWith(12.5)});it("shows an inline error for out-of-domain points and does not commit",()=>{const commit=vi.fn();render(<ProjectionPointsInput points={10} min={0} max={50} onCommit={commit}/>);const input=screen.getByLabelText("Fantasy points threshold");fireEvent.change(input,{target:{value:"60"}});fireEvent.blur(input);expect(screen.getByRole("alert").textContent).toContain("0.0 to 50.0");expect(commit).not.toHaveBeenCalled()});it("commits on Enter as well as blur",()=>{const commit=vi.fn();render(<ProjectionPointsInput points={10} min={0} max={50} onCommit={commit}/>);const input=screen.getByLabelText("Fantasy points threshold");fireEvent.change(input,{target:{value:"8"}});fireEvent.keyDown(input,{key:"Enter"});expect(commit).toHaveBeenCalledWith(8)});it("offers same-group entities when one is already selected",()=>{const rb1={...entity,entityKey:"rb1",name:"Example",position:"RB" as const};const rb2={...entity,entityKey:"rb2",name:"Runner Two",position:"RB" as const};const qb={...entity,entityKey:"qb",name:"Passer",position:"QB" as const};render(<ProjectionPicker entities={[qb,rb1,rb2]} selected={[rb1.entityKey]} onAdd={()=>{}}/>);fireEvent.focus(screen.getByLabelText("Add a projection"));expect(screen.getByText("Runner Two")).toBeTruthy()});it("hides entities outside the selected comparison group",()=>{const rb={...entity,entityKey:"rb",name:"Runner",position:"RB" as const};const qb={...entity,entityKey:"qb",name:"Passer",position:"QB" as const};render(<ProjectionPicker entities={[qb,rb]} selected={[rb.entityKey]} onAdd={()=>{}}/>);fireEvent.focus(screen.getByLabelText("Add a projection"));expect(screen.queryByText("Passer")).toBeNull()});it("explains when nothing is comparable with the selection",()=>{const rb={...entity,entityKey:"rb",name:"Runner",position:"RB" as const};const qb={...entity,entityKey:"qb",name:"Passer",position:"QB" as const};render(<ProjectionPicker entities={[qb,rb]} selected={[rb.entityKey,qb.entityKey]} onAdd={()=>{}}/>);expect(screen.getByText(/Only RBs, WRs and TEs can be compared with your current selection\./)).toBeTruthy()});
it("collapses suggestions once a player is selected",()=>{
 const add=vi.fn();
 const {rerender}=render(<ProjectionPicker entities={[entity]} selected={[]} onAdd={add}/>);
 expect(screen.getByText("Example")).toBeTruthy();
 rerender(<ProjectionPicker entities={[entity]} selected={[entity.entityKey]} onAdd={add}/>);
 expect(screen.queryByText("Example")).toBeNull();
});
it("brings suggestions back when the search box is focused",()=>{
 const other={...entity,entityKey:"e2",name:"Second Option"};
 render(<ProjectionPicker entities={[entity,other]} selected={[entity.entityKey]} onAdd={()=>{}}/>);
 const input=screen.getByLabelText("Add a projection");
 expect(screen.queryByText("Second Option")).toBeNull();
 fireEvent.focus(input);
 expect(screen.getByText("Second Option")).toBeTruthy();
 fireEvent.blur(input);
 expect(screen.queryByText("Second Option")).toBeNull();
});
it("collapses after a pick once the selection updates",()=>{
 const other={...entity,entityKey:"e2",name:"Second Option"};
 const add=vi.fn();
 const {rerender}=render(<ProjectionPicker entities={[entity,other]} selected={[]} onAdd={add}/>);
 fireEvent.focus(screen.getByLabelText("Add a projection"));
 fireEvent.click(screen.getByText("Example"));
 expect(add).toHaveBeenCalledWith(entity.entityKey);
 rerender(<ProjectionPicker entities={[entity,other]} selected={[entity.entityKey]} onAdd={add}/>);
 expect(screen.queryByText("Second Option")).toBeNull();
});
});

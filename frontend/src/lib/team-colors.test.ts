import { describe,expect,it } from "vitest";
import { assignTeamLineColors,readableTextOn,teamLinePalette,teamPrimaryColor,teamSecondaryColor } from "./team-colors";

describe("projection line colors",()=>{
 it("uses the top of the team swatch for a lone player",()=>{
  expect(teamLinePalette("CHI",1)).toEqual([teamPrimaryColor("CHI")]);
 });

 it("alternates the top and bottom swatch colors for two teammates",()=>{
  expect(teamLinePalette("CHI",2)).toEqual([teamPrimaryColor("CHI"),teamSecondaryColor("CHI")]);
 });

 it("keeps every same-team slot distinct",()=>{
  for(const count of [1,2,3,4,5,6]){
   const palette=teamLinePalette("CHI",count);
   expect(palette).toHaveLength(count);
   expect(new Set(palette).size).toBe(count);
  }
 });

 it("gives different teams different colors",()=>{
  const colors=assignTeamLineColors([
   {entityKey:"a",team:"CHI"},{entityKey:"b",team:"GB"},{entityKey:"c",team:"CHI"},
  ]);
  expect(colors.get("a")).toBe(teamPrimaryColor("CHI"));
  expect(colors.get("c")).toBe(teamSecondaryColor("CHI"));
  expect(colors.get("b")).toBe(teamPrimaryColor("GB"));
  expect(new Set(colors.values()).size).toBe(3);
 });

 it("falls back for an unknown team without colliding",()=>{
  const palette=teamLinePalette("XXX",4);
  expect(palette).toHaveLength(4);
  expect(new Set(palette).size).toBe(4);
 });
});

describe("readableTextOn",()=>{
 it("uses dark text on light team colours and white text on dark ones",()=>{
  // 49ers gold is light enough that white text would be unreadable.
  expect(readableTextOn(teamLinePalette("SF",2)[1]!)).toBe("#111827");
  expect(readableTextOn(teamLinePalette("CHI",2)[0]!)).toBe("#ffffff");
 });
 it("falls back to dark text when the colour cannot be parsed",()=>{
  expect(readableTextOn("not-a-colour")).toBe("#111827");
 });
});
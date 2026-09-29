import { describe, expect, it } from "vitest";
import { scenarioColors } from "./scenarioColors";

const builtIn = (name: string) => ({ name, saved_id: null });
const saved = (name: string, id: number) => ({ name, saved_id: id });
const slot = (n: number) => `var(--color-series-${n})`;

describe("scenarioColors", () => {
  it("gives the built-in scenarios fixed slots, whatever their position", () => {
    const colors = scenarioColors([builtIn("Higher income"), builtIn("Current plan")]);
    expect(colors.get("Current plan")).toBe(slot(1));
    expect(colors.get("Higher income")).toBe(slot(3));
  });

  it("gives saved scenarios the next slots in creation order", () => {
    const colors = scenarioColors([
      builtIn("Current plan"),
      builtIn("Higher contribution"),
      builtIn("Higher income"),
      saved("Later", 9),
      saved("Earlier", 2),
    ]);
    expect(colors.get("Earlier")).toBe(slot(4));
    expect(colors.get("Later")).toBe(slot(5));
  });

  it("never generates a ninth colour; built-in slots stay reserved", () => {
    const many = Array.from({ length: 7 }, (_, i) => saved(`Mine ${i}`, i + 1));
    const colors = scenarioColors([builtIn("Current plan"), ...many]);
    expect(colors.get("Mine 0")).toBe(slot(4)); // slots 2 and 3 belong to the built-ins
    expect(colors.get("Mine 4")).toBe(slot(8));
    expect(colors.has("Mine 5")).toBe(false);
    expect([...colors.values()].every((c) => /series-[1-8]\)$/.test(c))).toBe(true);
  });
});

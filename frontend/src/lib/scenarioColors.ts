/**
 * Colour per scenario. Colour follows the entity, never its position in a list: the
 * built-in scenarios always keep their slot, and saved scenarios take the next slots in
 * the order they were created (by id). The palette has 8 validated slots; scenarios
 * beyond that get no colour and appear in the table only (a 9th hue is never generated).
 */

const BUILT_IN_SLOTS: Record<string, number> = {
  "Current plan": 1,
  "Higher contribution": 2,
  "Higher income": 3,
};
const SLOTS = 8;

export type ColoredScenario = { name: string; saved_id: number | null };

export function scenarioColors(scenarios: ColoredScenario[]): Map<string, string> {
  const colors = new Map<string, string>();
  const used = new Set<number>();
  for (const s of scenarios) {
    const slot = BUILT_IN_SLOTS[s.name];
    if (slot && s.saved_id === null) {
      colors.set(s.name, `var(--color-series-${slot})`);
      used.add(slot);
    }
  }
  const saved = scenarios.filter((s) => s.saved_id !== null).sort((a, b) => a.saved_id! - b.saved_id!);
  let next = Object.keys(BUILT_IN_SLOTS).length + 1;
  for (const s of saved) {
    while (used.has(next)) next++;
    if (next > SLOTS) break;
    colors.set(s.name, `var(--color-series-${next})`);
    used.add(next);
  }
  return colors;
}

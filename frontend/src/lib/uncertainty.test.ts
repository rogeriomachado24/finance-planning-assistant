import { describe, expect, it } from "vitest";
import { uncertainty } from "../test/uncertaintyFixture";
import {
  goalDateRange,
  horizonEnd,
  probabilitySentence,
  reachedByRows,
  shareExplained,
  shortfallSentence,
  valueRange,
} from "./uncertainty";

describe("wording for simulated futures", () => {
  it("states the share with the number of futures and the target", () => {
    expect(probabilitySentence(uncertainty())).toBe(
      "of 1,000 simulated futures reach €80,000 by 1 Jun 2032",
    );
    expect(shareExplained(uncertainty())).toBe("95% means about 95 in every 100 simulated futures.");
    expect(shareExplained(uncertainty({ probability_by_target_date: 1 }))).toBeNull();
  });

  it("gives the range of goal dates", () => {
    expect(goalDateRange(uncertainty())).toBe(
      "In the middle 80% of futures, the goal is reached between Nov 2030 and Apr 2032 (in half of them by Jul 2031).",
    );
  });

  it("says when some futures don't reach the goal within the simulated period", () => {
    const late = uncertainty({
      goal_dates: { p10: "2035-03-01", p50: "2041-01-01", p90: null },
      not_reached_share: 0.27,
    });
    expect(horizonEnd(late)).toBe("Jun 2042");
    expect(goalDateRange(late)).toBe(
      "The goal is reached by Mar 2035 in 10% of futures, and in half of them by Jan 2041. In 27% of futures, it is not reached by Jun 2042.",
    );
    const never = uncertainty({ goal_dates: { p10: null, p50: null, p90: null }, not_reached_share: 0.95 });
    expect(goalDateRange(never)).toBe("In most simulated futures, the goal is not reached by Jun 2042.");
  });

  it("gives the value range and the size of the misses", () => {
    expect(valueRange(uncertainty())).toBe(
      "On 1 Jun 2032, cash + investments are between €81,725 and €105,378 in the middle 80% of futures (€92,122 in the middle one).",
    );
    expect(shortfallSentence(uncertainty())).toBe(
      "In the futures that miss the target date, they are typically €2,409 short (€5,964 or more in the worst tenth of those).",
    );
    expect(shortfallSentence(uncertainty({ shortfall_when_missed: null }))).toBeNull();
  });
});

describe("reachedByRows", () => {
  it("runs from the first futures to reach the goal to nearly all of them", () => {
    const rows = reachedByRows(uncertainty());
    expect(rows.map((r) => r.label)).toEqual([
      "By 1 Jan 2030",
      "By 1 Jan 2031",
      "By 1 Jan 2032",
      "By 1 Jun 2032 (target date)",
      "By 1 Jan 2033",
    ]);
    expect(rows.find((r) => r.isTarget)?.share).toBe(0.948);
  });

  it("thins long lists but keeps the target date and the last row", () => {
    const reached_by = Array.from({ length: 30 }, (_, i) => ({
      date: `${2027 + i}-01-01`,
      share: (i + 1) / 40,
    }));
    reached_by.splice(3, 0, { date: "2029-06-01", share: 0.09 });
    const rows = reachedByRows(uncertainty({ reached_by, target_date: "2029-06-01" }), 8);
    expect(rows.length).toBeLessThanOrEqual(10);
    expect(rows.some((r) => r.isTarget)).toBe(true);
    expect(rows.at(-1)?.key).toBe("2056-01-01");
  });

  it("always shows the target date, even when no future reaches the goal by then", () => {
    const rows = reachedByRows(
      uncertainty({
        reached_by: [
          { date: "2032-01-01", share: 0 },
          { date: "2032-06-01", share: 0 },
          { date: "2033-01-01", share: 0 },
        ],
      }),
    );
    expect(rows.map((r) => r.key)).toEqual(["2032-06-01", "2033-01-01"]);
  });
});

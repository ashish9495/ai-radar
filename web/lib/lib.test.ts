import { describe, expect, it } from "vitest";
import { formatIST, freshness, isOldNews, safeHref, timeAgo } from "./format";
import { parseInline, parseMarkdown } from "./markdown";
import { buildRpcArgs } from "./api";
import { DEMO_DISCOVERIES, demoSearch } from "./demo";

describe("format", () => {
  it("renders UTC timestamps in IST", () => {
    expect(formatIST("2026-10-24T02:30:00Z")).toContain("08:00");
    expect(formatIST(null)).toBe("Unknown");
  });
  it("freshness never reports stale data as fresh", () => {
    const now = new Date("2026-10-24T12:00:00Z");
    expect(freshness("2026-10-24T11:30:00Z", 30, now)).toBe("fresh");
    expect(freshness("2026-10-24T10:00:00Z", 30, now)).toBe("delayed");
    expect(freshness("2026-10-23T00:00:00Z", 30, now)).toBe("stale");
    expect(freshness(null, 30, now)).toBe("none");
  });
  it("timeAgo", () => {
    expect(timeAgo("2026-10-24T11:00:00Z", new Date("2026-10-24T12:00:00Z"))).toBe("1 h ago");
    expect(timeAgo("2026-10-24T11:30:00Z", new Date("2026-10-24T12:00:00Z"))).toBe("30 min ago");
    expect(timeAgo(null)).toBe("never");
  });
  it("detects newly discovered old news", () => {
    expect(isOldNews("2026-09-01T00:00:00Z", "2026-10-24T00:00:00Z")).toBe(true);
    expect(isOldNews(null, "2026-10-24T00:00:00Z")).toBe(false);
  });
  it("blocks non-http links", () => {
    expect(safeHref("javascript:alert(1)")).toBeUndefined();
    expect(safeHref("data:text/html,hi")).toBeUndefined();
    expect(safeHref("https://a.com/x")).toBe("https://a.com/x");
  });
});

describe("markdown", () => {
  it("parses links and drops unsafe hrefs", () => {
    const toks = parseInline("see [ok](https://a.com) and [bad](javascript:alert(1))");
    expect(toks.find((t) => t.t === "a")).toMatchObject({ href: "https://a.com/" });
    expect(toks.filter((t) => t.t === "a")).toHaveLength(1);
  });
  it("never produces raw HTML tokens", () => {
    const blocks = parseMarkdown("# Title\n- <img src=x onerror=alert(1)> item\nplain");
    expect(blocks.map((b) => b.t)).toEqual(["h", "li", "p"]);
    expect(JSON.stringify(blocks)).toContain("<img");  // kept as *text*, React escapes it
  });
});

describe("api args", () => {
  it("maps params to RPC argument names and clamps limit", () => {
    expect(buildRpcArgs({ q: " mcp ", types: ["tool"], limit: 500, offset: -5, hiddenGems: true })).toEqual({
      q: "mcp", p_types: ["tool"], p_sort: "discovered", p_limit: 100, p_offset: 0, p_hidden_gems: true,
    });
  });
  it("trims overly long search input", () => {
    expect(buildRpcArgs({ q: "x".repeat(500) }).q).toHaveLength(200);
  });
});

describe("demo data", () => {
  it("is clearly labelled as sample data", () => {
    expect(DEMO_DISCOVERIES.every((d) => d.title.startsWith("[SAMPLE]"))).toBe(true);
  });
  it("filters and paginates like the real RPC", () => {
    const all = demoSearch({});
    const tools = demoSearch({ types: ["tool"] });
    expect(tools.every((d) => d.discovery_type === "tool")).toBe(true);
    expect(demoSearch({ limit: 1 })).toHaveLength(1);
    expect(all[0].total_count).toBe(all.length);
  });
});

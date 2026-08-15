import assert from "node:assert/strict";
import { test } from "node:test";

import { runHotelSearch } from "../src/graph.js";

test("invalid JSON input yields UNAVAILABLE without throwing", async () => {
  const result = await runHotelSearch("not json");
  assert.equal(result.status, "UNAVAILABLE");
  assert.match(result.notes ?? "", /invalid JSON/);
});

test("missing required fields yields UNAVAILABLE", async () => {
  const result = await runHotelSearch(JSON.stringify({ destination: "Florianopolis" }));
  assert.equal(result.status, "UNAVAILABLE");
});

test("MCP unreachable yields UNAVAILABLE (no fabricated hotels)", async () => {
  const result = await runHotelSearch(
    JSON.stringify({
      destination: "Florianopolis",
      start_date: "2026-09-20",
      end_date: "2026-09-24",
      travelers: 2,
    }),
  );
  // No mcp-hotel-search running in this unit test process -> must degrade,
  // never invent hotel data (PROJECT_SPEC.md §31).
  assert.equal(result.status, "UNAVAILABLE");
  assert.equal(result.options.length, 0);
});

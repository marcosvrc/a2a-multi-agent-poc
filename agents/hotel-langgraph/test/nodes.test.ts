import assert from "node:assert/strict";
import { test } from "node:test";

import { filterResults } from "../src/nodes/filter.js";
import { parseRequest } from "../src/nodes/parse.js";
import { rankResults } from "../src/nodes/rank.js";
import type { HotelGraphStateType } from "../src/graphState.js";
import type { HotelOption } from "../src/schemas.js";

function baseState(overrides: Partial<HotelGraphStateType> = {}): HotelGraphStateType {
  return {
    rawInput: "",
    request: null,
    parseError: null,
    rawHotels: [],
    mcpError: null,
    filteredHotels: [],
    rankedHotels: [],
    response: null,
    ...overrides,
  };
}

test("parseRequest accepts a well-formed payload", () => {
  const state = baseState({
    rawInput: JSON.stringify({
      destination: "Florianopolis",
      start_date: "2026-09-20",
      end_date: "2026-09-24",
      travelers: 2,
      budget: 8000,
    }),
  });
  const out = parseRequest(state);
  assert.equal(out.parseError, null);
  assert.equal(out.request?.destination, "Florianopolis");
});

test("parseRequest rejects missing required fields", () => {
  const state = baseState({ rawInput: JSON.stringify({ destination: "Florianopolis" }) });
  const out = parseRequest(state);
  assert.ok(out.parseError);
});

const HOTELS: HotelOption[] = [
  { id: "H1", name: "A", price_per_night: 100, currency: "BRL", rating: 4.0 },
  { id: "H2", name: "B", price_per_night: 900, currency: "BRL", rating: 4.9 },
  { id: "H3", name: "C", price_per_night: 200, currency: "BRL", rating: 3.5 },
];

test("filterResults drops hotels over budget for the stay length", () => {
  const state = baseState({
    request: {
      destination: "X",
      start_date: "2026-01-01",
      end_date: "2026-01-05", // 4 nights
      travelers: 1,
      budget: 500, // 500 / 4 nights = 125/night max
    },
    rawHotels: HOTELS,
  });
  const out = filterResults(state);
  assert.deepEqual(
    out.filteredHotels?.map((h) => h.id),
    ["H1"],
  );
});

test("filterResults keeps all hotels when no budget given", () => {
  const state = baseState({
    request: { destination: "X", start_date: "2026-01-01", end_date: "2026-01-02", travelers: 1 },
    rawHotels: HOTELS,
  });
  const out = filterResults(state);
  assert.equal(out.filteredHotels?.length, 3);
});

test("rankResults orders by rating desc, price asc tiebreaker, capped at 5", () => {
  const state = baseState({ filteredHotels: HOTELS });
  const out = rankResults(state);
  assert.deepEqual(
    out.rankedHotels?.map((h) => h.id),
    ["H2", "H1", "H3"],
  );
});

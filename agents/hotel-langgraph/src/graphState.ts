import { Annotation } from "@langchain/langgraph";

import type { HotelOption, HotelSearchRequest } from "./schemas.js";

/**
 * State threaded through the LangGraph nodes
 * (parse_request -> search_hotels -> filter_results -> rank_results ->
 * build_response), per PROJECT_SPEC.md §5.3.
 */
export const HotelGraphState = Annotation.Root({
  rawInput: Annotation<string>(),
  request: Annotation<HotelSearchRequest | null>(),
  parseError: Annotation<string | null>(),
  rawHotels: Annotation<HotelOption[]>(),
  mcpError: Annotation<string | null>(),
  filteredHotels: Annotation<HotelOption[]>(),
  rankedHotels: Annotation<HotelOption[]>(),
  response: Annotation<{ status: string; options: HotelOption[]; notes: string } | null>(),
});

export type HotelGraphStateType = typeof HotelGraphState.State;

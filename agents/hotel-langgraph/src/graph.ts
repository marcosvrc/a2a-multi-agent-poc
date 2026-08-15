import { END, START, StateGraph } from "@langchain/langgraph";

import { HotelGraphState } from "./graphState.js";
import { buildResponse } from "./nodes/build.js";
import { filterResults } from "./nodes/filter.js";
import { parseRequest } from "./nodes/parse.js";
import { rankResults } from "./nodes/rank.js";
import { searchHotelsNode } from "./nodes/search.js";
import type { HotelResult } from "./schemas.js";

/**
 * Explicit stateful flow required by PROJECT_SPEC.md §5.3:
 *
 *   parse_request -> search_hotels -> filter_results -> rank_results -> build_response
 */
const graph = new StateGraph(HotelGraphState)
  .addNode("parse_request", parseRequest)
  .addNode("search_hotels", searchHotelsNode)
  .addNode("filter_results", filterResults)
  .addNode("rank_results", rankResults)
  .addNode("build_response", buildResponse)
  .addEdge(START, "parse_request")
  .addEdge("parse_request", "search_hotels")
  .addEdge("search_hotels", "filter_results")
  .addEdge("filter_results", "rank_results")
  .addEdge("rank_results", "build_response")
  .addEdge("build_response", END);

export const hotelGraph = graph.compile();

export async function runHotelSearch(rawInput: string): Promise<HotelResult> {
  const result = await hotelGraph.invoke({ rawInput });
  return result.response as HotelResult;
}

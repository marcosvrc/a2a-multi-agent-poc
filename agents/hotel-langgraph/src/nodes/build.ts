import type { HotelGraphStateType } from "../graphState.js";

/**
 * build_response node (PROJECT_SPEC.md §5.3): final step of the state
 * machine, produces the HotelResult-shaped object.
 */
export function buildResponse(state: HotelGraphStateType): Partial<HotelGraphStateType> {
  if (state.parseError) {
    return { response: { status: "UNAVAILABLE", options: [], notes: state.parseError } };
  }
  if (state.mcpError) {
    return { response: { status: "UNAVAILABLE", options: [], notes: state.mcpError } };
  }
  if (state.rankedHotels.length === 0) {
    // Distinguish "MCP genuinely had nothing for this destination" from
    // "MCP had hotels, but none fit the traveler's budget" — collapsing
    // both into UNAVAILABLE made a legitimate empty-after-filter result
    // (and everything downstream: the Planner's overall PARTIAL, the
    // Budget Agent's "hotel-agent did not return SUCCESS" note) look
    // identical to a real outage.
    if (state.rawHotels.length > 0) {
      return {
        response: {
          status: "PARTIAL",
          options: [],
          notes: "no hotels within the given budget",
        },
      };
    }
    return {
      response: {
        status: "UNAVAILABLE",
        options: [],
        notes: "no hotels found for this destination",
      },
    };
  }
  return { response: { status: "SUCCESS", options: state.rankedHotels, notes: "" } };
}

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
    return {
      response: {
        status: "UNAVAILABLE",
        options: [],
        notes: "no hotels matched the given criteria",
      },
    };
  }
  return { response: { status: "SUCCESS", options: state.rankedHotels, notes: "" } };
}

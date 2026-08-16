import type { HotelGraphStateType } from "../graphState.js";

/**
 * filter_results node (PROJECT_SPEC.md §5.3): applies the budget
 * criterion when the caller provided one. A hotel is kept if its total
 * stay cost (price_per_night * nights) fits within the traveler's
 * budget; nights is derived from start/end date. Hotels are never
 * dropped for a missing budget (PARTIAL/UNKNOWN would be for the Budget
 * Agent to decide, not this one — §5.5 vs §5.3 scope).
 */
export function filterResults(state: HotelGraphStateType): Partial<HotelGraphStateType> {
  if (!state.request || state.mcpError) {
    return { filteredHotels: [] };
  }
  const { budget, start_date: startDate, end_date: endDate } = state.request;

  if (budget === undefined) {
    return { filteredHotels: state.rawHotels };
  }

  const rawNights = Math.round((Date.parse(endDate) - Date.parse(startDate)) / (1000 * 60 * 60 * 24));
  if (Number.isNaN(rawNights)) {
    // Defense in depth: the ISO-date regex in schemas.ts should already
    // reject this upstream, but never silently treat "unparseable dates"
    // as "every hotel is unaffordable" if that guard is ever bypassed.
    return { filteredHotels: state.rawHotels };
  }
  const nights = Math.max(1, rawNights);

  const filtered = state.rawHotels.filter((h) => h.price_per_night * nights <= budget);
  return { filteredHotels: filtered };
}

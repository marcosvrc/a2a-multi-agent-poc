import type { HotelGraphStateType } from "../graphState.js";

/**
 * rank_results node (PROJECT_SPEC.md §5.3): ranks by rating desc, then
 * price ascending as a tiebreaker, capped at 5 options.
 */
export function rankResults(state: HotelGraphStateType): Partial<HotelGraphStateType> {
  const ranked = [...state.filteredHotels]
    .sort((a, b) => {
      const ratingDiff = (b.rating ?? 0) - (a.rating ?? 0);
      if (ratingDiff !== 0) return ratingDiff;
      return a.price_per_night - b.price_per_night;
    })
    .slice(0, 5);
  return { rankedHotels: ranked };
}

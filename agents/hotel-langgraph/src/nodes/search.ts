import { settings } from "../config.js";
import { McpHotelSearchError, searchHotels } from "../mcpClient.js";
import type { HotelGraphStateType } from "../graphState.js";
import type { HotelOption } from "../schemas.js";

/**
 * search_hotels node (PROJECT_SPEC.md §5.3): calls MCP Hotel Search.
 * Never fabricates hotel data (§31) — MCP failure surfaces as mcpError
 * and downstream nodes degrade to UNAVAILABLE.
 */
export async function searchHotelsNode(state: HotelGraphStateType): Promise<Partial<HotelGraphStateType>> {
  if (!state.request) {
    return { mcpError: "no valid request to search with" };
  }
  const req = state.request;

  try {
    const raw = await searchHotels(
      settings.mcpHotelUrl,
      {
        destination: req.destination,
        start_date: req.start_date,
        end_date: req.end_date,
        guests: req.travelers,
      },
      settings.requestTimeoutSeconds * 1000,
    );

    const options: HotelOption[] = raw.hotels.map((h) => ({
      id: h.id,
      name: h.name,
      price_per_night: h.price_per_night,
      currency: h.currency,
      rating: h.rating,
      location: h.location,
    }));
    return { rawHotels: options, mcpError: null };
  } catch (err) {
    const message = err instanceof McpHotelSearchError ? err.message : (err as Error).message;
    return { rawHotels: [], mcpError: `MCP unavailable: ${message}` };
  }
}

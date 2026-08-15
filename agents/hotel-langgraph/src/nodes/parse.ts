import { HotelSearchRequestSchema } from "../schemas.js";
import type { HotelGraphStateType } from "../graphState.js";

/**
 * parse_request node (PROJECT_SPEC.md §5.3): validates the minimum
 * criteria — destino, datas, quantidade de hóspedes, orçamento,
 * localização, preferências (budget/location/preferences are optional
 * inputs the later nodes use when present).
 */
export function parseRequest(state: HotelGraphStateType): Partial<HotelGraphStateType> {
  let raw: unknown;
  try {
    raw = JSON.parse(state.rawInput);
  } catch (err) {
    return { parseError: `invalid JSON: ${(err as Error).message}` };
  }

  const result = HotelSearchRequestSchema.safeParse(raw);
  if (!result.success) {
    return { parseError: `invalid hotel search request: ${result.error.message}` };
  }
  return { request: result.data, parseError: null };
}

import { z } from "zod";

// Mirrors contracts/schemas/travel-request.schema.json (the subset the
// Hotel Agent needs). Kept intentionally close to /contracts — do not
// fork field names without updating the shared schema and explaining the
// incompatibility (PROJECT_SPEC.md §42 rule 6).
// A non-ISO date (e.g. "20/09/2026") used to pass `z.string().min(1)`
// silently, then turned into `Date.parse(...) === NaN` downstream in
// filter.ts — which made every hotel fail the budget filter and get
// reported as "no hotels matched the given criteria" (a validation bug
// disguised as a legitimate empty result). Reject it at parse time
// instead.
const isoDate = z.string().regex(/^\d{4}-\d{2}-\d{2}$/, "must be an ISO-8601 date (YYYY-MM-DD)");

export const HotelSearchRequestSchema = z.object({
  destination: z.string().min(1),
  start_date: isoDate,
  end_date: isoDate,
  travelers: z.number().int().min(1).default(1),
  budget: z.number().min(0).optional(),
  currency: z.string().optional(),
  preferences: z.array(z.string()).optional(),
});
export type HotelSearchRequest = z.infer<typeof HotelSearchRequestSchema>;

export const HotelOptionSchema = z.object({
  id: z.string(),
  name: z.string(),
  price_per_night: z.number(),
  currency: z.string(),
  rating: z.number().optional(),
  location: z.string().optional(),
});
export type HotelOption = z.infer<typeof HotelOptionSchema>;

// Mirrors contracts/schemas/hotel-result.schema.json.
export const HotelResultSchema = z.object({
  status: z.enum(["SUCCESS", "PARTIAL", "UNAVAILABLE", "UNKNOWN"]),
  options: z.array(HotelOptionSchema),
  notes: z.string().optional(),
});
export type HotelResult = z.infer<typeof HotelResultSchema>;

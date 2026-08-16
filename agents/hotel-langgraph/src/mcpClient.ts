import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";

export class McpHotelSearchError extends Error {}

export interface RawHotel {
  id: string;
  name: string;
  price_per_night: number;
  currency: string;
  rating?: number;
  location?: string;
  destination?: string;
}

export interface RawHotelSearchResult {
  provider: string;
  hotels: RawHotel[];
  notes?: string;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * One connect+callTool attempt. Opens a fresh client/transport (a failed
 * connection/handshake can't be reused for a retry) and always closes it
 * afterwards — the underlying SSE stream otherwise keeps the Node event
 * loop (and this agent's HTTP request) hanging open indefinitely.
 */
async function _attempt(
  mcpUrl: string,
  args: { destination: string; start_date: string; end_date: string; guests: number },
  timeoutMs: number,
): Promise<RawHotelSearchResult> {
  const transport = new StreamableHTTPClientTransport(new URL(mcpUrl));
  const client = new Client({ name: "hotel-agent", version: "0.1.0" });

  try {
    // `callTool`'s `{ timeout }` option only bounds the tool call itself —
    // `connect()` has no deadline of its own, so an MCP server that
    // accepts the TCP connection but never completes the MCP handshake
    // (hung container, half-open connection) would otherwise block this
    // agent's request indefinitely, never reaching `callTool` at all.
    await Promise.race([
      client.connect(transport),
      new Promise<never>((_, reject) =>
        setTimeout(() => reject(new McpHotelSearchError(`MCP connect timed out after ${timeoutMs}ms`)), timeoutMs),
      ),
    ]);
    const result = await client.callTool(
      { name: "search_hotels", arguments: args },
      undefined,
      { timeout: timeoutMs },
    );

    if (result.isError) {
      throw new McpHotelSearchError(`MCP tool returned an error: ${JSON.stringify(result.content)}`);
    }

    if (result.structuredContent) {
      return result.structuredContent as unknown as RawHotelSearchResult;
    }

    const content = result.content as Array<{ type: string; text?: string }> | undefined;
    const textBlock = content?.find((c) => c.type === "text");
    if (!textBlock?.text) {
      throw new McpHotelSearchError("MCP tool returned no parseable content");
    }
    return JSON.parse(textBlock.text) as RawHotelSearchResult;
  } catch (err) {
    if (err instanceof McpHotelSearchError) throw err;
    throw new McpHotelSearchError((err as Error).message);
  } finally {
    await client.close().catch(() => undefined);
  }
}

/**
 * Calls the MCP Hotel Search tool over Streamable HTTP.
 *
 * Fase 8 (PROJECT_SPEC.md §27 "Resiliência"): retries on any failure,
 * with exponential backoff, up to `retryAttempts` extra tries —
 * search_hotels is a pure read, safe to retry without the
 * non-idempotent-call caveat that applies to A2A `message/send` (see
 * planner-adk/app/a2a/client.py, the Python side of this same §27 rule).
 */
export async function searchHotels(
  mcpUrl: string,
  args: { destination: string; start_date: string; end_date: string; guests: number },
  timeoutMs: number,
  retryAttempts = 2,
  retryBackoffBaseMs = 500,
): Promise<RawHotelSearchResult> {
  let lastErr: unknown;
  for (let attempt = 0; attempt <= retryAttempts; attempt++) {
    try {
      return await _attempt(mcpUrl, args, timeoutMs);
    } catch (err) {
      lastErr = err;
      if (attempt >= retryAttempts) break;
      const delay = retryBackoffBaseMs * 2 ** attempt;
      // eslint-disable-next-line no-console
      console.warn(
        `MCP search_hotels failed (attempt ${attempt + 1}/${retryAttempts + 1}): ${(err as Error).message} — retrying in ${delay}ms`,
      );
      await sleep(delay);
    }
  }
  throw lastErr;
}

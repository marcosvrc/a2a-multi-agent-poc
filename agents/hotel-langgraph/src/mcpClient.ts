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

/**
 * Calls the MCP Hotel Search tool over Streamable HTTP. Opens a fresh
 * client/transport per call and always closes it afterwards — the
 * underlying SSE stream otherwise keeps the Node event loop (and this
 * agent's HTTP request) hanging open indefinitely.
 */
export async function searchHotels(
  mcpUrl: string,
  args: { destination: string; start_date: string; end_date: string; guests: number },
  timeoutMs: number,
): Promise<RawHotelSearchResult> {
  const transport = new StreamableHTTPClientTransport(new URL(mcpUrl));
  const client = new Client({ name: "hotel-agent", version: "0.1.0" });

  try {
    await client.connect(transport);
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

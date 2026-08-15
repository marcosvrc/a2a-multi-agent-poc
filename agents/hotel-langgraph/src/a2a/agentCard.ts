import type { AgentCard } from "./models.js";

export function buildAgentCard(publicUrl: string): AgentCard {
  return {
    name: "hotel-agent",
    description:
      "Searches, filters and ranks hotel options for a trip. Only handles hotels — never flights, activities or budget.",
    version: "0.1.0",
    url: publicUrl,
    protocol_version: "0.3",
    capabilities: { streaming: false, push_notifications: false },
    skills: [
      {
        id: "search_hotels",
        name: "Search Hotels",
        description:
          "Searches for hotels based on destination, dates, guest count, budget, location and preferences via MCP Hotel Search, returns ranked options.",
        tags: ["hotel", "specialist"],
      },
    ],
    default_input_modes: ["text/plain", "application/json"],
    default_output_modes: ["text/plain", "application/json"],
  };
}

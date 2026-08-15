import express from "express";

import { buildAgentCard } from "./a2a/agentCard.js";
import { buildAgentCardRouter, buildJsonRpcRouter, InMemoryTaskStore } from "./a2a/server.js";
import { handleMessage } from "./agent.js";
import { settings } from "./config.js";
import { setupTracing } from "./telemetry.js";

setupTracing();

const app = express();
app.use(express.json());

const card = buildAgentCard(settings.publicUrl);
const taskStore = new InMemoryTaskStore();

app.use(buildAgentCardRouter(card));
app.use(buildJsonRpcRouter(handleMessage, taskStore));

app.get("/health", (_req, res) => {
  res.json({ status: "UP" });
});

app.get("/ready", (_req, res) => {
  res.json({ status: "READY", dependencies: { mcp_hotel: settings.mcpHotelUrl } });
});

app.listen(settings.port, "0.0.0.0", () => {
  // eslint-disable-next-line no-console
  console.log(`{"level":"INFO","message":"${settings.serviceName} listening on :${settings.port}"}`);
});

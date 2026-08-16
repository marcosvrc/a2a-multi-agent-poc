export const settings = {
  serviceName: process.env.SERVICE_NAME ?? "hotel-agent",
  port: Number(process.env.PORT ?? "8003"),
  publicUrl: process.env.PUBLIC_URL ?? "http://localhost:8003",
  mcpHotelUrl: process.env.MCP_HOTEL_URL ?? "http://mcp-hotel:9002/mcp",
  requestTimeoutSeconds: Number(process.env.AGENT_REQUEST_TIMEOUT_SECONDS ?? "30"),
  logLevel: process.env.LOG_LEVEL ?? "INFO",
  otelExporterOtlpEndpoint: process.env.OTEL_EXPORTER_OTLP_ENDPOINT ?? "http://otel-collector:4318",
  otelServiceNamespace: process.env.OTEL_SERVICE_NAMESPACE ?? "a2a-poc",
  otelSdkDisabled: (process.env.OTEL_SDK_DISABLED ?? "false").toLowerCase() === "true",
  // Fase 9 (§7/§56 "M6 Security"): see src/a2a/auth.ts for what each mode
  // does. "dev" (spec default) requires DEV_AGENT_TOKEN on every /a2a
  // call; "jwt" requires a valid HS256 JWT instead.
  authMode: process.env.AUTH_MODE ?? "dev",
  devAgentToken: process.env.DEV_AGENT_TOKEN ?? "local-development-only",
  jwtSecret: process.env.JWT_SECRET ?? "local-development-only-change-me",
};

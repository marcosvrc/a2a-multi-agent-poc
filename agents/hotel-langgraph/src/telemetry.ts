import { OTLPTraceExporter } from "@opentelemetry/exporter-trace-otlp-http";
import { ExpressInstrumentation } from "@opentelemetry/instrumentation-express";
import { HttpInstrumentation } from "@opentelemetry/instrumentation-http";
import { resourceFromAttributes } from "@opentelemetry/resources";
import { NodeSDK } from "@opentelemetry/sdk-node";

import { settings } from "./config.js";

/**
 * OpenTelemetry bootstrap for the Hotel Agent — same shape as the Python
 * agents' telemetry.py (service.name/service.namespace resource, OTLP
 * exporter to the local otel-collector, HTTP/Express auto-instrumentation).
 * Uses the OTLP/HTTP exporter (port 4318) rather than gRPC (4317) to avoid
 * pulling in a native gRPC dependency for a single POC agent.
 */
export function setupTracing(): NodeSDK | null {
  if (settings.otelSdkDisabled) {
    return null;
  }

  const sdk = new NodeSDK({
    resource: resourceFromAttributes({
      "service.name": settings.serviceName,
      "service.namespace": settings.otelServiceNamespace,
    }),
    traceExporter: new OTLPTraceExporter({ url: `${settings.otelExporterOtlpEndpoint}/v1/traces` }),
    instrumentations: [new HttpInstrumentation(), new ExpressInstrumentation()],
  });

  try {
    sdk.start();
  } catch (err) {
    // eslint-disable-next-line no-console
    console.warn(`{"level":"WARNING","message":"failed to start OpenTelemetry SDK: ${(err as Error).message}"}`);
    return null;
  }
  return sdk;
}

import type { Request } from "express";
import jwt from "jsonwebtoken";

/**
 * Service-to-service auth for the A2A endpoint (PROJECT_SPEC.md §7/§56
 * "M6 Security", Fase 9) — TypeScript mirror of
 * agents/*-python/app/auth.py (dev/jwt/none modes, identical semantics)
 * so hotel-agent enforces the same contract as every Python agent.
 *
 * Only the POST /a2a route is gated. /health, /ready and
 * /.well-known/agent-card.json stay open on purpose, so Agent Card
 * discovery (§9) and health/readiness checks work before any caller has
 * a token.
 *
 * See docs/adr/ADR-015-security-jwt-agent-identity-oidc-spike.md for the
 * rationale (why dev/jwt/none, why not a full external IdP yet).
 */

export interface AuthConfig {
  authMode: string;
  devToken: string;
  jwtSecret: string;
}

export class AuthError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "AuthError";
  }
}

function extractBearerToken(req: Request): string | undefined {
  const header = req.headers["authorization"];
  const value = Array.isArray(header) ? header[0] : header;
  if (!value || !value.toLowerCase().startsWith("bearer ")) {
    return undefined;
  }
  return value.slice("bearer ".length).trim();
}

/**
 * Verifies an incoming /a2a request. Throws AuthError on failure
 * (caller is responsible for mapping that to a 401 JSON-RPC response).
 * Returns the caller's identity (JWT `sub`) when known, or undefined.
 */
export function verifyRequest(req: Request, config: AuthConfig): string | undefined {
  const mode = (config.authMode || "dev").trim().toLowerCase();
  if (mode === "none") {
    return undefined;
  }

  const token = extractBearerToken(req);
  if (token === undefined) {
    throw new AuthError("missing Authorization: Bearer <token> header");
  }

  if (mode === "jwt") {
    try {
      const claims = jwt.verify(token, config.jwtSecret, { algorithms: ["HS256"] });
      if (typeof claims === "string") {
        return undefined;
      }
      return typeof claims.sub === "string" ? claims.sub : undefined;
    } catch (err) {
      throw new AuthError(`invalid JWT: ${(err as Error).message}`);
    }
  }

  if (token !== config.devToken) {
    throw new AuthError("invalid token");
  }
  return undefined;
}

/**
 * Mints the token hotel-agent would attach to any outgoing A2A call it
 * makes (kept for parity with the Python agents' mint_outgoing_token;
 * hotel-agent does not currently delegate to other agents over A2A, but
 * this keeps the module a complete mirror).
 */
export function mintOutgoingToken(
  config: AuthConfig,
  agentId: string,
  ttlSeconds = 300,
): string {
  const mode = (config.authMode || "dev").trim().toLowerCase();
  if (mode === "jwt") {
    const now = Math.floor(Date.now() / 1000);
    return jwt.sign({ sub: agentId, iat: now, exp: now + ttlSeconds }, config.jwtSecret, {
      algorithm: "HS256",
    });
  }
  return config.devToken;
}

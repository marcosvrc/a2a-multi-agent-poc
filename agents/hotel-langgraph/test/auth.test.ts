import assert from "node:assert/strict";
import { test } from "node:test";

import jwt from "jsonwebtoken";

import { AuthError, mintOutgoingToken, verifyRequest } from "../src/a2a/auth.js";

const DEV_CONFIG = { authMode: "dev", devToken: "dev-secret", jwtSecret: "jwt-secret" };
const JWT_CONFIG = { authMode: "jwt", devToken: "dev-secret", jwtSecret: "jwt-secret" };
const NONE_CONFIG = { authMode: "none", devToken: "dev-secret", jwtSecret: "jwt-secret" };

function fakeRequest(authorization?: string) {
  return { headers: authorization ? { authorization } : {} } as import("express").Request;
}

test("none mode never checks the header", () => {
  assert.equal(verifyRequest(fakeRequest(), NONE_CONFIG), undefined);
});

test("dev mode rejects a missing header", () => {
  assert.throws(() => verifyRequest(fakeRequest(), DEV_CONFIG), AuthError);
});

test("dev mode rejects the wrong token", () => {
  assert.throws(() => verifyRequest(fakeRequest("Bearer wrong"), DEV_CONFIG), AuthError);
});

test("dev mode accepts the configured token", () => {
  assert.equal(verifyRequest(fakeRequest("Bearer dev-secret"), DEV_CONFIG), undefined);
});

test("jwt mode rejects a missing header", () => {
  assert.throws(() => verifyRequest(fakeRequest(), JWT_CONFIG), AuthError);
});

test("jwt mode rejects a token signed with the wrong secret", () => {
  const token = jwt.sign({ sub: "flight-agent" }, "wrong-secret", { algorithm: "HS256" });
  assert.throws(() => verifyRequest(fakeRequest(`Bearer ${token}`), JWT_CONFIG), AuthError);
});

test("jwt mode rejects an expired token", () => {
  const token = jwt.sign({ sub: "flight-agent" }, "jwt-secret", {
    algorithm: "HS256",
    expiresIn: -10,
  });
  assert.throws(() => verifyRequest(fakeRequest(`Bearer ${token}`), JWT_CONFIG), AuthError);
});

test("jwt mode accepts a valid token and returns the caller identity", () => {
  const token = jwt.sign({ sub: "flight-agent" }, "jwt-secret", { algorithm: "HS256" });
  assert.equal(verifyRequest(fakeRequest(`Bearer ${token}`), JWT_CONFIG), "flight-agent");
});

test("mintOutgoingToken returns the dev token in dev mode", () => {
  assert.equal(mintOutgoingToken(DEV_CONFIG, "hotel-agent"), "dev-secret");
});

test("mintOutgoingToken round trips through verifyRequest in jwt mode", () => {
  const token = mintOutgoingToken(JWT_CONFIG, "hotel-agent");
  const sub = verifyRequest(fakeRequest(`Bearer ${token}`), JWT_CONFIG);
  assert.equal(sub, "hotel-agent");
});

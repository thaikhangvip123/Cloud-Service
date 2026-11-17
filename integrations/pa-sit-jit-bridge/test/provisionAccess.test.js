import assert from "node:assert/strict";
import { createHmac } from "node:crypto";
import test from "node:test";

import {
  buildProvisionPayload,
  sendProvisionRequest,
} from "../src/backend/provisionAccess.js";

const ENDPOINT =
  "https://example.execute-api.ap-southeast-1.amazonaws.com/sit/provision-access";

const VALID_INPUT = {
  requestId: "JIRA-123",
  requester: "user@example.com",
  awsAccount: "application",
  accessType: "PowerUser",
  durationHours: "2",
};

const ENVIRONMENT = {
  AWS_JIT_ENDPOINT: ENDPOINT,
  AWS_JIT_API_KEY: "test-api-key",
  WEBHOOK_HMAC_SECRET: "test-hmac-secret",
};

test("buildProvisionPayload normalizes the Jira Automation inputs", () => {
  assert.deepEqual(buildProvisionPayload(VALID_INPUT), {
    ...VALID_INPUT,
    durationHours: 2,
  });
});

test("buildProvisionPayload rejects an unsupported access type", () => {
  assert.throws(
    () => buildProvisionPayload({ ...VALID_INPUT, accessType: "SuperAdmin" }),
    /accessType must be ReadOnly, PowerUser, or Admin/,
  );
});

test("buildProvisionPayload rejects a duration outside the system limit", () => {
  assert.throws(
    () => buildProvisionPayload({ ...VALID_INPUT, durationHours: "12.1" }),
    /durationHours must be greater than zero and no more than 12/,
  );
});

test("sendProvisionRequest signs the exact JSON body sent to API Gateway", async () => {
  let capturedRequest;
  const fetchImplementation = async (url, options) => {
    capturedRequest = { url, options };
    return {
      ok: true,
      status: 200,
      text: async () =>
        JSON.stringify({
          status: "success",
          requestId: "JIRA-123",
          durationTier: "2h",
          expiresAt: "2026-11-13T12:00:00Z",
          identityCenterPortalUrl: "https://example.awsapps.com/start",
        }),
    };
  };

  const result = await sendProvisionRequest(VALID_INPUT, {
    environment: ENVIRONMENT,
    fetchImplementation,
    now: () => 1_700_000_000_000,
  });

  const expectedSignature = createHmac("sha256", ENVIRONMENT.WEBHOOK_HMAC_SECRET)
    .update(`1700000000.${capturedRequest.options.body}`, "utf8")
    .digest("hex");

  assert.equal(capturedRequest.url, ENDPOINT);
  assert.equal(capturedRequest.options.headers["x-api-key"], ENVIRONMENT.AWS_JIT_API_KEY);
  assert.equal(capturedRequest.options.headers["x-request-timestamp"], "1700000000");
  assert.equal(
    capturedRequest.options.headers["x-jira-signature"],
    `sha256=${expectedSignature}`,
  );
  assert.equal(result.status, "success");
});

test("sendProvisionRequest fails closed when a secret variable is missing", async () => {
  await assert.rejects(
    sendProvisionRequest(VALID_INPUT, {
      environment: { ...ENVIRONMENT, WEBHOOK_HMAC_SECRET: "" },
      fetchImplementation: async () => assert.fail("fetch must not run"),
    }),
    /WEBHOOK_HMAC_SECRET is not configured/,
  );
});

test("sendProvisionRequest surfaces a safe AWS error code", async () => {
  await assert.rejects(
    sendProvisionRequest(VALID_INPUT, {
      environment: ENVIRONMENT,
      fetchImplementation: async () => ({
        ok: false,
        status: 403,
        text: async () => JSON.stringify({ status: "error", errorCode: "AUTHENTICATION_ERROR" }),
      }),
    }),
    /AWS JIT provisioning failed \(AUTHENTICATION_ERROR\)/,
  );
});

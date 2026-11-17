import { createHmac } from "node:crypto";

const ALLOWED_ACCESS_TYPES = new Set(["ReadOnly", "PowerUser", "Admin"]);
const REQUEST_TIMEOUT_MS = 25_000;
const SIT_API_HOST_SUFFIX = ".execute-api.ap-southeast-1.amazonaws.com";
const SIT_API_PATH = "/sit/provision-access";

function requiredString(value, fieldName) {
  if (typeof value !== "string" || value.trim() === "") {
    throw new Error(`${fieldName} is required`);
  }
  return value.trim();
}

function requiredEnvironmentVariable(environment, name) {
  const value = environment[name];
  if (typeof value !== "string" || value === "") {
    throw new Error(`Forge variable ${name} is not configured`);
  }
  return value;
}

function validateEndpoint(value) {
  let endpoint;
  try {
    endpoint = new URL(value);
  } catch {
    throw new Error("AWS_JIT_ENDPOINT must be a valid HTTPS URL");
  }

  if (
    endpoint.protocol !== "https:" ||
    !endpoint.hostname.endsWith(SIT_API_HOST_SUFFIX) ||
    endpoint.pathname !== SIT_API_PATH ||
    endpoint.search ||
    endpoint.hash ||
    endpoint.username ||
    endpoint.password
  ) {
    throw new Error("AWS_JIT_ENDPOINT must be the SIT API Gateway provision-access endpoint");
  }
  return endpoint.toString();
}

export function buildProvisionPayload(input) {
  const requestId = requiredString(input?.requestId, "requestId");
  const requester = requiredString(input?.requester, "requester");
  const awsAccount = requiredString(input?.awsAccount, "awsAccount");
  const accessType = requiredString(input?.accessType, "accessType");
  const durationHours = Number(input?.durationHours);

  if (!requester.includes("@")) {
    throw new Error("requester must be an email address");
  }
  if (!ALLOWED_ACCESS_TYPES.has(accessType)) {
    throw new Error("accessType must be ReadOnly, PowerUser, or Admin");
  }
  if (!Number.isFinite(durationHours) || durationHours <= 0 || durationHours > 12) {
    throw new Error("durationHours must be greater than zero and no more than 12");
  }

  return {
    requestId,
    requester,
    awsAccount,
    accessType,
    durationHours,
  };
}

export async function sendProvisionRequest(
  input,
  {
    environment = process.env,
    fetchImplementation = fetch,
    now = Date.now,
  } = {},
) {
  const endpoint = validateEndpoint(
    requiredEnvironmentVariable(environment, "AWS_JIT_ENDPOINT"),
  );
  const apiKey = requiredEnvironmentVariable(environment, "AWS_JIT_API_KEY");
  const hmacSecret = requiredEnvironmentVariable(environment, "WEBHOOK_HMAC_SECRET");
  const body = JSON.stringify(buildProvisionPayload(input));
  const timestamp = Math.floor(now() / 1000).toString();
  const signature = createHmac("sha256", hmacSecret)
    .update(`${timestamp}.${body}`, "utf8")
    .digest("hex");

  const response = await fetchImplementation(endpoint, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-api-key": apiKey,
      "x-request-timestamp": timestamp,
      "x-jira-signature": `sha256=${signature}`,
    },
    body,
    signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
  });

  const responseText = await response.text();
  let result = {};
  if (responseText) {
    try {
      result = JSON.parse(responseText);
    } catch {
      throw new Error(`AWS JIT API returned invalid JSON with HTTP ${response.status}`);
    }
  }

  if (!response.ok || result.status !== "success") {
    const errorCode = result.errorCode || `HTTP_${response.status}`;
    throw new Error(`AWS JIT provisioning failed (${errorCode})`);
  }

  return result;
}

export async function provisionAccess(payload) {
  const requestId = typeof payload?.requestId === "string" ? payload.requestId : "unknown";
  console.log(JSON.stringify({
    level: "INFO",
    operation: "provision_access",
    requestId,
    message: "Forwarding approved Jira request to the AWS JIT API",
  }));

  const result = await sendProvisionRequest(payload);

  console.log(JSON.stringify({
    level: "INFO",
    operation: "provision_access",
    requestId: result.requestId,
    status: result.status,
    message: "AWS JIT API completed the provisioning request",
  }));
  return result;
}

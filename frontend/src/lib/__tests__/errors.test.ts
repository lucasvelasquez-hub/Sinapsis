import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiFetch } from "../api";
import { describeApiError } from "../errors";

function mockFetch(impl: () => Promise<Response>) {
  vi.stubGlobal("fetch", vi.fn(impl));
}

afterEach(() => {
  vi.unstubAllGlobals();
});

async function apiErrorOf(path: string): Promise<ApiError> {
  const err: unknown = await apiFetch(path).catch((e: unknown) => e);
  expect(err).toBeInstanceOf(ApiError);
  return err as ApiError;
}

describe("apiFetch", () => {
  it("throws ApiError with status and backend error code", async () => {
    mockFetch(async () =>
      new Response(
        JSON.stringify({
          error: { code: "SERVICE_ALREADY_DECIDED", message: "Service 'S-1' already has status DISPATCHED." },
        }),
        { status: 409 }
      )
    );

    const err = await apiErrorOf("/decisions");

    expect(err.status).toBe(409);
    expect(err.code).toBe("SERVICE_ALREADY_DECIDED");
    expect(err.message).toContain("DISPATCHED");
  });

  it("falls back to HTTP status when the body is not JSON", async () => {
    mockFetch(async () => new Response("boom", { status: 502 }));

    const err = await apiErrorOf("/health");

    expect(err.status).toBe(502);
    expect(err.code).toBe("HTTP_ERROR");
  });

  it("wraps network failures as NETWORK_ERROR", async () => {
    mockFetch(async () => {
      throw new TypeError("Failed to fetch");
    });

    const err = await apiErrorOf("/health");

    expect(err.status).toBe(0);
    expect(err.code).toBe("NETWORK_ERROR");
  });
});

describe("describeApiError", () => {
  it("explains an already decided service", () => {
    const d = describeApiError(new ApiError(409, "SERVICE_ALREADY_DECIDED", "x"));

    expect(d.title).toMatch(/ya tiene una decisión/i);
    expect(d.retryable).toBe(false);
  });

  it("marks network errors as retryable", () => {
    const d = describeApiError(new ApiError(0, "NETWORK_ERROR", "Failed to fetch"));

    expect(d.title).toMatch(/conectar/i);
    expect(d.retryable).toBe(true);
  });

  it("shows the backend message for unknown domain errors", () => {
    const d = describeApiError(new ApiError(400, "DOMAIN_ERROR", "assigned_unit_id is required"));

    expect(d.message).toBe("assigned_unit_id is required");
  });

  it("handles non-API errors", () => {
    expect(describeApiError(new Error("raro")).message).toBe("raro");
  });
});

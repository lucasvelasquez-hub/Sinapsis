import { beforeEach, describe, expect, it } from "vitest";

import { normalizeDispatcherId, useDispatcherStore } from "../dispatcherStore";

describe("normalizeDispatcherId", () => {
  it("trims and accepts the backend pattern", () => {
    expect(normalizeDispatcherId("  desp-07 ")).toBe("desp-07");
    expect(normalizeDispatcherId("ana.perez@central")).toBe("ana.perez@central");
  });

  it("rejects empty, too short or invalid identifiers", () => {
    expect(normalizeDispatcherId("")).toBeNull();
    expect(normalizeDispatcherId("   ")).toBeNull();
    expect(normalizeDispatcherId("a")).toBeNull();
    expect(normalizeDispatcherId("con espacio")).toBeNull();
    expect(normalizeDispatcherId("x".repeat(65))).toBeNull();
  });
});

describe("useDispatcherStore", () => {
  beforeEach(() => {
    localStorage.clear();
    useDispatcherStore.setState({ dispatcherId: "" });
  });

  it("persists the dispatcher id", () => {
    useDispatcherStore.getState().setDispatcherId("desp-07");

    expect(localStorage.getItem("core-dispatcher")).toContain("desp-07");
  });
});

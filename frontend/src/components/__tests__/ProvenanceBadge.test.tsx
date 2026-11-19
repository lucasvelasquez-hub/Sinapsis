import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ProvenanceBadge } from "../ProvenanceBadge";

describe("ProvenanceBadge", () => {
  it("renders the provenance label", () => {
    render(<ProvenanceBadge type="SIMULADO" />);
    expect(screen.getByText("SIMULADO")).toBeTruthy();
  });
});

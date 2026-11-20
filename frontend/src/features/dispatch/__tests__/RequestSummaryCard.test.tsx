import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { RequestSummaryCard } from "../RequestSummaryCard";
import { detail } from "./testUtils";

function withContext(overrides: Record<string, unknown>) {
  const d = detail("SIM-0004");
  return { ...d, context: { ...d.context, ...overrides } };
}

describe("RequestSummaryCard", () => {
  it("shows the exact request time and whether it is peak hour", () => {
    render(<RequestSummaryCard detail={detail("SIM-0004")} />);

    expect(screen.getByText("23:47, fuera de hora pico")).toBeTruthy();
  });

  it("marks peak hour", () => {
    render(<RequestSummaryCard detail={withContext({ is_peak_hour: true })} />);

    expect(screen.getByText("23:47, hora pico")).toBeTruthy();
  });

  it.each([
    ["LOW", "Baja"],
    ["MODERATE", "Moderada"],
    ["HIGH", "Alta"],
  ])("shows zone demand pressure %s as %s", (level, label) => {
    render(<RequestSummaryCard detail={withContext({ demand_pressure_level: level })} />);

    expect(screen.getByText(label)).toBeTruthy();
  });

  it("the info button reveals the 4h, 8h and 12h counts", () => {
    render(<RequestSummaryCard detail={detail("SIM-0004")} />);
    const info = screen.getByRole("button", { name: /detalle de la demanda/i });

    expect(info.getAttribute("aria-expanded")).toBe("false");
    expect(screen.queryByText(/1 en 4h, 2 en 8h, 5 en 12h/)).toBeNull();
    fireEvent.click(info);

    expect(info.getAttribute("aria-expanded")).toBe("true");
    expect(screen.getByText(/1 en 4h, 2 en 8h, 5 en 12h/)).toBeTruthy();
  });
});

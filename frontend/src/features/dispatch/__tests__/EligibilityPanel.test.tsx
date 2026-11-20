import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { EligibilityPanel } from "../EligibilityPanel";
import { eligibility } from "./testUtils";

const EXCLUDED = [
  { id: "MOV-002", reason: "Turno TURNO_DIA no cubre las 23:00" },
  { id: "MOV-005", reason: "Turno TURNO_DIA no cubre las 23:00" },
  { id: "MOV-008", reason: "Ocupada hasta 01:11" },
];

describe("EligibilityPanel", () => {
  it("shows eligible units and keeps exclusions folded", () => {
    render(
      <EligibilityPanel
        eligibility={eligibility(["MOV-024", "MOV-012"], EXCLUDED)}
      />,
    );

    expect(screen.getByText("MOV-024")).toBeTruthy();
    expect(screen.getByText("MOV-012")).toBeTruthy();
    expect(screen.queryByText(/Ocupada hasta/)).toBeNull();
    expect(
      screen
        .getByRole("button", { name: /excluidas \(3\)/i })
        .getAttribute("aria-expanded"),
    ).toBe("false");
  });

  it("unfolds the exclusions with their reasons on click", () => {
    render(
      <EligibilityPanel eligibility={eligibility(["MOV-024"], EXCLUDED)} />,
    );

    fireEvent.click(screen.getByRole("button", { name: /excluidas \(3\)/i }));

    expect(screen.getByText(/Ocupada hasta 01:11/)).toBeTruthy();
    expect(screen.getAllByText(/TURNO_DIA no cubre/)).toHaveLength(2);
  });

  it("without eligible units says so and shows why every unit was excluded", () => {
    render(<EligibilityPanel eligibility={eligibility([], EXCLUDED)} />);

    expect(screen.getByText(/sin unidades elegibles/i)).toBeTruthy();
    expect(screen.getByText(/Ocupada hasta 01:11/)).toBeTruthy();
  });
});

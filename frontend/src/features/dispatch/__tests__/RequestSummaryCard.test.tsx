import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { RequestSummaryCard } from "../RequestSummaryCard";
import { detail } from "./testUtils";

describe("RequestSummaryCard", () => {
  it("shows zone demand in the 4h, 8h and 12h windows", () => {
    render(<RequestSummaryCard detail={detail("SIM-0004")} />);

    expect(screen.getByText(/1 en 4h, 2 en 8h, 5 en 12h/)).toBeTruthy();
  });
});

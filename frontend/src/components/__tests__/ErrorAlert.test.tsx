import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api";

import { ErrorAlert } from "../ErrorAlert";

describe("ErrorAlert", () => {
  it("renders nothing without an error", () => {
    const { container } = render(<ErrorAlert error={null} />);

    expect(container.firstChild).toBeNull();
  });

  it("announces the error as an alert with its description", () => {
    render(<ErrorAlert error={new ApiError(409, "SERVICE_ALREADY_DECIDED", "detalle")} />);

    const alert = screen.getByRole("alert");
    expect(alert.textContent).toMatch(/ya tiene una decisión/i);
  });

  it("offers retry only for retryable errors", () => {
    const onRetry = vi.fn();
    const { rerender } = render(
      <ErrorAlert error={new ApiError(0, "NETWORK_ERROR", "Failed")} onRetry={onRetry} />
    );

    fireEvent.click(screen.getByRole("button", { name: /reintentar/i }));
    expect(onRetry).toHaveBeenCalledOnce();

    rerender(<ErrorAlert error={new ApiError(409, "SERVICE_ALREADY_DECIDED", "x")} onRetry={onRetry} />);
    expect(screen.queryByRole("button", { name: /reintentar/i })).toBeNull();
  });
});

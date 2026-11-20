import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api";

import { ErrorAlert, QueryErrorAlert } from "../ErrorAlert";

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

describe("QueryErrorAlert", () => {
  const ok = () => ({ error: null, refetch: vi.fn() });
  const failing = (status: number, code: string) => ({
    error: new ApiError(status, code, "fallo"),
    refetch: vi.fn(),
  });

  it("renders nothing when every query is fine", () => {
    const { container } = render(<QueryErrorAlert queries={[ok(), ok()]} />);

    expect(container.firstChild).toBeNull();
  });

  it("shows the first error and retries only the failing queries", () => {
    const good = ok();
    const bad1 = failing(0, "NETWORK_ERROR");
    const bad2 = failing(502, "HTTP_ERROR");
    render(<QueryErrorAlert queries={[good, bad1, bad2]} />);

    expect(screen.getByRole("alert").textContent).toMatch(/conectar/i);
    fireEvent.click(screen.getByRole("button", { name: /reintentar/i }));

    expect(good.refetch).not.toHaveBeenCalled();
    expect(bad1.refetch).toHaveBeenCalledOnce();
    expect(bad2.refetch).toHaveBeenCalledOnce();
  });

  it("shows failureReason while React Query is still retrying", () => {
    const retrying = {
      error: null,
      failureReason: new ApiError(0, "NETWORK_ERROR", "Failed"),
      refetch: vi.fn(),
    };
    render(<QueryErrorAlert queries={[retrying]} />);

    expect(screen.getByRole("alert").textContent).toMatch(/conectar/i);
  });
});

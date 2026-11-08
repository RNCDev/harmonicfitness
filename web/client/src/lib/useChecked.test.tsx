import { describe, expect, it, vi } from "vitest";
import { act, renderHook } from "@testing-library/react";
import type { FormEvent } from "react";
import { useChecked } from "./useChecked";

const long = (v: string) => (v.length < 8 ? "At least eight characters." : null);
const submitEvent = () => ({ preventDefault: vi.fn() }) as unknown as FormEvent;

describe("useChecked", () => {
  it("says nothing while they first type, then each rule's message once they've tried to send", () => {
    const { result } = renderHook(() => useChecked());
    expect(result.current.check(long, "short")).toBeNull();
    const e = submitEvent(), send = vi.fn();
    act(() => result.current.submit(e, send));
    expect(e.preventDefault).toHaveBeenCalled();
    expect(send).toHaveBeenCalledTimes(1);   // send re-checks the rules itself
    expect(result.current.tried).toBe(true);
    expect(result.current.check(long, "short")).toBe("At least eight characters.");
    expect(result.current.check(long, "long enough")).toBeNull();   // updates as they type
  });

  it("goes back to untried on reset", () => {
    const { result } = renderHook(() => useChecked());
    act(() => result.current.submit(submitEvent(), () => {}));
    act(() => result.current.reset());
    expect(result.current.tried).toBe(false);
    expect(result.current.check(long, "short")).toBeNull();
  });
});

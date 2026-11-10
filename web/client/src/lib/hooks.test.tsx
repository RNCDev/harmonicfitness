// What the shared hooks promise every page: an action's busy and words, a load that keeps what it has, the focus
// trap, and the page's address.
import { describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, renderHook, screen, waitFor } from "@testing-library/react";
import { useRef, useState } from "react";
import { ApiError, NotSignedIn } from "./api";
import { useAction } from "./useAction";
import { useFocusTrap } from "./useFocusTrap";
import { usePage } from "./usePage";
import { useResource } from "./useResource";

describe("useAction", () => {
  it("is busy while it runs and true when it went through", async () => {
    let finish!: () => void;
    const { result } = renderHook(() => useAction(() => new Promise<void>((r) => { finish = r; })));
    let ran!: Promise<boolean>;
    act(() => { ran = result.current.run(); });
    expect(result.current.busy).toBe(true);
    await act(async () => { finish(); });
    expect(await ran).toBe(true);
    expect(result.current.busy).toBe(false);
  });

  it("says the server's words for a refusal, and its own when there are none", async () => {
    const { result, rerender } = renderHook(({ e }) => useAction(() => Promise.reject(e), { fallback: "Couldn't save." }),
      { initialProps: { e: new ApiError(409, "Someone else changed it.") as unknown } });
    await act(async () => { await result.current.run(); });
    expect(result.current.error).toBe("Someone else changed it.");
    rerender({ e: new TypeError("Failed to fetch") });
    await act(async () => { await result.current.run(); });
    expect(result.current.error).toBe("Couldn't save.");
  });

  it("says nothing for a lost session: the page has gone to sign-in", async () => {
    const { result } = renderHook(() => useAction(() => Promise.reject(new NotSignedIn())));
    await act(async () => { expect(await result.current.run()).toBe(false); });
    expect(result.current.error).toBeNull();
  });
});

describe("useResource", () => {
  it("refresh keeps the answer while it asks again, and says a failure beside it", async () => {
    const load = vi.fn().mockResolvedValueOnce(["Monday"]).mockRejectedValueOnce(new TypeError("offline"))
      .mockResolvedValueOnce(["Monday", "Tuesday"]);
    const { result } = renderHook(() => useResource(load, "Couldn't load your workouts."));
    await waitFor(() => expect(result.current.data).toEqual(["Monday"]));
    await act(async () => { await result.current.refresh(); });
    expect(result.current.data).toEqual(["Monday"]);
    expect(result.current.error).toBe("Couldn't load your workouts.");
    await act(async () => { await result.current.refresh(); });
    expect(result.current.data).toEqual(["Monday", "Tuesday"]);
    expect(result.current.error).toBeNull();
  });
});

function Trap({ onEscape }: { onEscape: () => void }) {
  const [open, setOpen] = useState(false);
  const panel = useRef<HTMLDivElement>(null);
  const opener = useRef<HTMLButtonElement>(null);
  useFocusTrap(panel, open, { onEscape: () => { onEscape(); setOpen(false); }, returnFocus: opener });
  return (
    <>
      <button ref={opener} onClick={() => setOpen(true)}>Open</button>
      {/* mounted throughout, as the Settings drawer is, and hidden while closed */}
      <div ref={panel} hidden={!open}><button>First</button><button>Last</button></div>
    </>
  );
}

describe("useFocusTrap", () => {
  it("moves focus in, keeps Tab inside, closes on Escape and gives focus back", () => {
    const onEscape = vi.fn();
    render(<Trap onEscape={onEscape} />);
    const opener = screen.getByRole("button", { name: "Open" });
    opener.focus();
    fireEvent.click(opener);
    expect(screen.getByRole("button", { name: "First" })).toHaveFocus();
    screen.getByRole("button", { name: "Last" }).focus();
    fireEvent.keyDown(document, { key: "Tab" });
    expect(screen.getByRole("button", { name: "First" })).toHaveFocus();
    fireEvent.keyDown(document, { key: "Tab", shiftKey: true });
    expect(screen.getByRole("button", { name: "Last" })).toHaveFocus();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onEscape).toHaveBeenCalled();
    expect(opener).toHaveFocus();
  });
});

describe("usePage", () => {
  it("keeps the page in the address, and follows the back button", () => {
    const { result } = renderHook(() => usePage());
    expect(result.current[0]).toBe("chat");
    act(() => result.current[1]("logs"));
    expect(window.location.hash).toBe("#logs");
    expect(result.current[0]).toBe("logs");
    act(() => {
      window.history.replaceState(null, "", "/");
      window.dispatchEvent(new PopStateEvent("popstate"));
    });
    expect(result.current[0]).toBe("chat");
  });
});

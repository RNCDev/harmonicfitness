import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { Empty, Loadable, Notice } from "./Notice";

describe("Notice", () => {
  it("announces an error at once and anything else politely, and draws nothing without words", () => {
    const { container, rerender } = render(<Notice tone="error">Couldn't save that.</Notice>);
    expect(screen.getByRole("alert")).toHaveTextContent("Couldn't save that.");
    rerender(<Notice tone="busy">Loading…</Notice>);
    expect(screen.getByRole("status")).toHaveAttribute("aria-busy", "true");
    rerender(<Notice tone="done">{null}</Notice>);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("Loadable", () => {
  const list = (v: string[]) => <ul>{v.map((x) => <li key={x}>{x}</li>)}</ul>;

  it("says what's loading, a failure with Try again, keeps content on a later failure, and shows the empty state", () => {
    const { rerender } = render(<Loadable value={null} what="your workouts">{list}</Loadable>);
    expect(screen.getByRole("status")).toHaveTextContent("Loading your workouts…");

    // a first failure: the reason and Try again in place of the content
    const retry = vi.fn();
    rerender(<Loadable value={null} error="Couldn't load your workouts." onRetry={retry} what="your workouts">{list}</Loadable>);
    expect(screen.getByRole("alert")).toHaveTextContent("Couldn't load your workouts.");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(retry).toHaveBeenCalled();

    // a later read that fails keeps the content and says so above it
    rerender(<Loadable value={["Monday"]} error="Couldn't load your workouts." onRetry={() => {}} what="your workouts">
      {list}</Loadable>);
    expect(screen.getByText("Monday")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("Couldn't load your workouts.");
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();

    rerender(<Loadable value={[] as string[]} what="your workouts" isEmpty={(v) => v.length === 0}
      empty={<Empty>Nothing yet.</Empty>}>{list}</Loadable>);
    expect(screen.getByText("Nothing yet.")).toBeInTheDocument();
  });
});

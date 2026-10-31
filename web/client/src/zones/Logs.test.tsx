import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { arrange, Logs } from "./Logs";
import { api, ApiError, type Workout } from "../api";

vi.mock("../api", async (orig) => {
  const real = await orig<typeof import("../api")>();
  return { ...real, api: { workouts: vi.fn(), workoutScript: vi.fn(), workoutFeedback: vi.fn(),
    rateWorkout: vi.fn(), deleteWorkout: vi.fn() } };
});

const m = api as unknown as Record<"workouts" | "workoutScript" | "workoutFeedback" | "rateWorkout" | "deleteWorkout",
  ReturnType<typeof vi.fn>>;

const W = (over: Partial<Workout>): Workout => ({ n: 1, date: "2026-10-30", minutes: 15, kit: "home", coach: "Coach Reed",
  format: "intervals", movements: ["easy spin", "seated climb"], topics: "Sixers", build_id: "aaa111", feedback: [],
  rating: null, has_script: true, ...over });
const LIST = [W({}), W({ n: 2, date: "2026-10-29", minutes: 25, format: "circuit", kit: "gym", build_id: "bbb222",
  movements: ["goblet squat"], rating: "positive", feedback: ["loved it"] }),
  W({ n: 3, date: "2026-10-28", minutes: 10, build_id: null, rating: "negative", has_script: false })];

beforeEach(() => {
  vi.clearAllMocks();
  m.workouts.mockResolvedValue(LIST);
  m.workoutScript.mockResolvedValue("Evening. Fifteen minutes on the bike.");
  for (const k of ["workoutFeedback", "rateWorkout", "deleteWorkout"] as const) m[k].mockResolvedValue(undefined);
});

const cards = () => screen.getAllByRole("listitem").filter((li) => li.classList.contains("logs-card"));

describe("arrange", () => {
  it("filters by words, rating, format and kit, and sorts", () => {
    expect(arrange(LIST, "goblet", "all", "all", "all", "newest").map((w) => w.n)).toEqual([2]);
    expect(arrange(LIST, "", "unrated", "all", "all", "newest").map((w) => w.n)).toEqual([1]);
    expect(arrange(LIST, "", "all", "intervals", "home", "oldest").map((w) => w.n)).toEqual([3, 1]);
    expect(arrange(LIST, "", "all", "all", "all", "longest").map((w) => w.n)).toEqual([2, 1, 3]);
    expect(arrange(LIST, "", "all", "all", "all", "best").map((w) => w.n)).toEqual([2, 3, 1]);
    expect(arrange(LIST, "", "all", "all", "all", "worst").map((w) => w.n)).toEqual([3, 2, 1]);
  });
});

describe("the Logs page", () => {
  it("lists the workouts newest first and filters them", async () => {
    render(<Logs onClose={() => {}} onSignedOut={() => {}} />);
    await waitFor(() => expect(cards()).toHaveLength(3));
    expect(screen.getByText("3 of 3 workouts")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Rating"), { target: { value: "positive" } });
    expect(cards()).toHaveLength(1);
    expect(cards()[0]).toHaveTextContent("loved it");
    fireEvent.change(screen.getByLabelText("Rating"), { target: { value: "all" } });
    fireEvent.change(screen.getByLabelText("Search"), { target: { value: "nothing like this" } });
    expect(screen.getByText(/No workouts match/)).toBeInTheDocument();
  });

  it("rates, and a second press clears the rating", async () => {
    render(<Logs onClose={() => {}} onSignedOut={() => {}} />);
    await waitFor(() => expect(cards()).toHaveLength(3));
    const first = cards()[0];
    fireEvent.click(within(first).getByRole("button", { name: "Positive" }));
    await waitFor(() => expect(m.rateWorkout).toHaveBeenCalledWith("aaa111", "positive"));
    const second = cards()[1];
    fireEvent.click(within(second).getByRole("button", { name: "Positive" }));
    await waitFor(() => expect(m.rateWorkout).toHaveBeenCalledWith("bbb222", "none"));
  });

  it("puts a refused rating back and says why", async () => {
    m.rateWorkout.mockRejectedValue(new ApiError(409, "Your files changed at the same moment. Try again."));
    render(<Logs onClose={() => {}} onSignedOut={() => {}} />);
    await waitFor(() => expect(cards()).toHaveLength(3));
    const btn = within(cards()[0]).getByRole("button", { name: "Neutral" });
    fireEvent.click(btn);
    expect(await screen.findByRole("alert")).toHaveTextContent("Try again");
    await waitFor(() => expect(btn).toHaveAttribute("aria-pressed", "false"));
  });

  it("shows the script, saves feedback and deletes after a confirm", async () => {
    render(<Logs onClose={() => {}} onSignedOut={() => {}} />);
    await waitFor(() => expect(cards()).toHaveLength(3));
    const first = cards()[0];
    fireEvent.click(within(first).getByRole("button", { name: "Show the script" }));
    expect(await within(first).findByText(/Fifteen minutes on the bike/)).toBeInTheDocument();
    expect(within(cards()[2]).getByRole("button", { name: "Show the script" })).toBeDisabled();

    fireEvent.change(within(first).getByLabelText("Feedback on this workout"), { target: { value: "too long" } });
    fireEvent.click(within(first).getByRole("button", { name: "Save" }));
    await waitFor(() => expect(m.workoutFeedback).toHaveBeenCalledWith("aaa111", "too long"));

    fireEvent.click(within(cards()[2]).getByRole("button", { name: "Delete" }));
    expect(m.deleteWorkout).not.toHaveBeenCalled();
    fireEvent.click(within(cards()[2]).getByRole("button", { name: "Delete it" }));
    await waitFor(() => expect(m.deleteWorkout).toHaveBeenCalledWith("3"));   // no build id: its number
  });
});

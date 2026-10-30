import { describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { Chat, stepsOf } from "./Chat";

const base = { lines: [], working: false, error: null, noKey: false, onSend: () => {}, onOpenKeys: () => {} };

describe("the chat", () => {
  it("sends a line and shows Thinking while working", () => {
    const onSend = vi.fn();
    const { rerender } = render(<Chat {...base} lines={[{ role: "agent", text: "Hello there" }]} onSend={onSend} />);
    expect(screen.getByText("Hello there")).toBeInTheDocument();
    const box = screen.getByRole("textbox", { name: "Message" });
    fireEvent.change(box, { target: { value: "  my knee is sore " } });
    fireEvent.keyDown(box, { key: "Enter", shiftKey: true });
    expect(onSend).not.toHaveBeenCalled();
    fireEvent.keyDown(box, { key: "Enter" });
    expect(onSend).toHaveBeenCalledWith("my knee is sore");
    expect(box).toHaveValue("");

    rerender(<Chat {...base} working onSend={onSend} />);
    expect(screen.getByText(/Your coach is working…/)).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Message" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
  });

  it("shows the coach's steps while it works, the latest last", () => {
    const steps = Array.from({ length: 8 }, (_, i) => ({ text: `step ${i + 1}` }));
    render(<Chat {...base} working steps={steps} />);
    expect(screen.queryByText("step 1")).toBeNull();
    expect(screen.getByText("2 earlier steps")).toBeInTheDocument();
    expect(screen.getByText("step 8")).not.toHaveClass("now");   // finished: none is running
  });

  it("renders the coach's Markdown: tables, bold, lists", () => {
    const md = "**Plan**\n\n| Block | Time |\n|---|---|\n| Spine | 60 s |\n\n- one\n- two";
    render(<Chat {...base} lines={[{ role: "agent", text: md }]} />);
    expect(screen.getByText("Plan").tagName).toBe("STRONG");
    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "Spine" })).toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
  });

  it("collapses repeated steps", () => {
    render(<Chat {...base} working steps={[{ text: "Reading" }, { text: "Reading" }, { text: "Writing" }]} />);
    expect(screen.getAllByText("Reading")).toHaveLength(1);
  });

  it("plays and offers a workout's audio until it expires", () => {
    const later = new Date(Date.now() + 3600_000).toISOString();
    const { container, rerender } = render(<Chat {...base} lines={[{ role: "agent", text: "",
      audio: { id: "abc", name: "Workout 5 min", expires_at: later } }]} />);
    expect(container.querySelector("audio")?.getAttribute("src")).toBe("/api/media/abc");
    expect(screen.getByRole("link", { name: "Download the MP3" })).toHaveAttribute("href", "/api/media/abc?download=1");
    rerender(<Chat {...base} lines={[{ role: "agent", text: "",
      audio: { id: "abc", name: "Workout 5 min", expires_at: "2020-01-01T00:00:00Z" } }]} />);
    expect(container.querySelector("audio")).toBeNull();
    expect(screen.getByText(/has expired/)).toBeInTheDocument();
  });

  it("offers the priced recording with its price, and records on the button", () => {
    const onRecord = vi.fn();
    render(<Chat {...base} offer={{ name: "Workout 5 min", coach: "Coach Reed", chars: 3000, usd: 0.045,
      service: "fish" }} onRecord={onRecord} />);
    expect(screen.getByText(/3,000 characters on Fish Audio, about \$0.05/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Record it (about $0.05)" }));
    expect(onRecord).toHaveBeenCalled();
  });

  it("Stop sits beside Send while the coach works, and only then", () => {
    const { rerender, container } = render(<Chat {...base} working onStop={() => {}} />);
    const form = container.querySelector(".chat-form")!;
    expect(form).toContainElement(screen.getByRole("button", { name: "Stop" }));
    rerender(<Chat {...base} working={false} onStop={() => {}} />);
    expect(screen.queryByRole("button", { name: "Stop" })).toBeNull();
  });

  it("offers the waiting conversation on the first screen", () => {
    const onResume = vi.fn();
    render(<Chat {...base} waiting={{ offer: false, at: null }} onResume={onResume} />);
    fireEvent.click(screen.getByRole("button", { name: /Pick up where you left off/ }));
    expect(onResume).toHaveBeenCalledTimes(1);
    expect(screen.getByText("Your coach asked you something.")).toBeInTheDocument();
  });

  it("Stop says it's stopping and asks once", () => {
    const onStop = vi.fn();
    render(<Chat {...base} working onStop={onStop} />);
    fireEvent.click(screen.getByRole("button", { name: "Stop" }));
    expect(onStop).toHaveBeenCalledTimes(1);
    expect(screen.getByText(/Stopping…/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Stop" })).toBeNull();
  });

  it("never renders the listener's own line as Markdown", () => {
    render(<Chat {...base} lines={[{ role: "user", text: "**not bold**" }]} />);
    expect(screen.getByText("**not bold**")).toBeInTheDocument();
  });

  it("shows the no-key message with a Settings button", () => {
    const onOpenKeys = vi.fn();
    render(<Chat {...base} noKey error="Add a key for Claude in Settings first." onOpenKeys={onOpenKeys} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Add a key for Claude in Settings first.");
    fireEvent.click(screen.getByRole("button", { name: "Open Settings" }));
    expect(onOpenKeys).toHaveBeenCalled();
  });

  it("with no key, welcomes and offers the three writers, and the box waits", () => {
    const onAddKey = vi.fn();
    const need = [{ name: "Claude", service: "anthropic", voice: false }, { name: "ChatGPT", service: "openai", voice: false },
      { name: "Gemini", service: "gemini", voice: true }];
    render(<Chat {...base} needsKey={need} onAddKey={onAddKey} />);
    expect(screen.getByRole("heading", { name: "Welcome to HarmonicFitness" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Gemini/ })).toHaveTextContent("Free key from Google AI Studio. Also voices a coach");
    expect(screen.getByRole("button", { name: /^Claude/ })).toHaveTextContent("Paid key");
    expect(screen.queryByRole("region", { name: "Plan a workout" })).toBeNull();
    expect(screen.getByRole("textbox", { name: "Message" })).toBeDisabled();
    expect(screen.getByRole("textbox", { name: "Message" })).toHaveAttribute("placeholder", "Add a key in Settings first");
    fireEvent.click(screen.getByRole("button", { name: /^ChatGPT/ }));
    expect(onAddKey).toHaveBeenCalledWith("openai");
  });

  it("with a key, offers the starter sentence once it knows what to fill it with", () => {
    const { rerender } = render(<Chat {...base} needsKey={null} />);
    expect(screen.queryByRole("region", { name: "Plan a workout" })).toBeNull();
    rerender(<Chat {...base} needsKey={null} start={{ coaches: [], kits: [], minutes: 25, limits: [], suggest: null, setup_quick: false }} />);
    expect(screen.getByRole("region", { name: "Plan a workout" })).toBeInTheDocument();
    expect(screen.queryByText("Welcome to HarmonicFitness")).toBeNull();
    expect(screen.getByRole("textbox", { name: "Message" })).toBeEnabled();
  });

  it("shows a running step as current, and a finished one as done", () => {
    const steps = stepsOf([
      { stage: "step", text: "Reading", id: 1, state: "running" }, { stage: "step", text: "Reading", id: 1, state: "done" },
      { stage: "step", text: "Checking", id: 2, state: "running" }, { stage: "step", text: "Checking", id: 2, state: "failed", failed: true },
      { stage: "step", text: "Recording your workout", id: 3, state: "running" },
    ]);
    expect(steps).toEqual([{ text: "Reading", failed: false, running: false, think: false, key: "s1" },
      { text: "Checking", failed: true, running: false, think: false, key: "s2" },
      { text: "Recording your workout", failed: false, running: true, think: false, key: "s3" }]);
    render(<Chat {...base} working steps={steps} />);
    expect(screen.getByText("Recording your workout")).toHaveClass("now");
    expect(screen.getByText("Reading")).not.toHaveClass("now");
    expect(screen.getByText("Checking")).toHaveClass("bad");
  });

  it("reads a step from before ids as done", () => {
    expect(stepsOf([{ stage: "folder" }, { stage: "step", text: "Old", failed: false }]))
      .toEqual([{ text: "Old", failed: false, running: false, think: false, key: "i0" }]);
  });

  it("shows what the coach is thinking about only while it thinks", () => {
    const ev = [
      { stage: "step", text: "Reading your message", id: 1, state: "running", think: true },
      { stage: "step", text: "Reading your message", id: 1, state: "done", think: true },
      { stage: "step", text: "Working out today's safe moves", id: 2, state: "running" },
      { stage: "step", text: "Working out today's safe moves", id: 2, state: "done" },
      { stage: "step", text: "Writing your script", id: 3, state: "running", think: true },
    ];
    const { rerender } = render(<Chat {...base} working steps={stepsOf(ev)} />);
    expect(screen.queryByText(/Reading your message/)).toBeNull();      // done thinking is dropped
    expect(screen.getByText("Working out today's safe moves")).not.toHaveClass("now");
    expect(screen.getByText("Writing your script…")).toHaveClass("now", "think");
    rerender(<Chat {...base} working steps={stepsOf([...ev, { stage: "step", text: "Writing your script", id: 3, state: "done", think: true }])} />);
    expect(screen.queryByText(/Writing your script/)).toBeNull();
  });

  it("a long wait shows its own clock and says it's a long one", () => {
    vi.useFakeTimers();
    try {
      render(<Chat {...base} working steps={stepsOf([{ stage: "step", text: "Recording your workout", id: 1, state: "running" }])} />);
      expect(screen.queryByText("Recording a full workout takes a few minutes.")).toBeNull();
      act(() => { vi.advanceTimersByTime(30_000); });
      expect(screen.getByText("Recording a full workout takes a few minutes.")).toBeInTheDocument();
      expect(screen.getByText("Recording your workout")).toHaveTextContent(/30s$/);
    } finally {
      vi.useRealTimers();
    }
  });

  it("keeps the unsent text across a reload, and clears it on send", () => {
    sessionStorage.clear();
    const onSend = vi.fn();
    const { unmount } = render(<Chat {...base} onSend={onSend} />);
    fireEvent.change(screen.getByRole("textbox", { name: "Message" }), { target: { value: "20 minutes, legs" } });
    unmount();
    render(<Chat {...base} onSend={onSend} />);
    const box = screen.getByRole("textbox", { name: "Message" });
    expect(box).toHaveValue("20 minutes, legs");
    fireEvent.keyDown(box, { key: "Enter" });
    expect(onSend).toHaveBeenCalledWith("20 minutes, legs");
    expect(sessionStorage.getItem("hf-chat-draft")).toBeNull();
  });
});

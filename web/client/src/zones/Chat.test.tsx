import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { Chat } from "./Chat";

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
    expect(screen.getByText(/Working…/)).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Message" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
  });

  it("shows the coach's steps while it works, the latest last", () => {
    const steps = Array.from({ length: 8 }, (_, i) => ({ text: `step ${i + 1}` }));
    render(<Chat {...base} working steps={steps} />);
    expect(screen.queryByText("step 1")).toBeNull();
    expect(screen.getByText("2 earlier steps")).toBeInTheDocument();
    expect(screen.getByText("step 8")).toHaveClass("now");
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

  it("never renders the listener's own line as Markdown", () => {
    render(<Chat {...base} lines={[{ role: "user", text: "**not bold**" }]} />);
    expect(screen.getByText("**not bold**")).toBeInTheDocument();
  });

  it("shows the no-key message with a Keys button", () => {
    const onOpenKeys = vi.fn();
    render(<Chat {...base} noKey error="Add a key for Claude in Keys first." onOpenKeys={onOpenKeys} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Add a key for Claude in Keys first.");
    fireEvent.click(screen.getByRole("button", { name: "Open Keys" }));
    expect(onOpenKeys).toHaveBeenCalled();
  });
});

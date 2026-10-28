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
    expect(screen.getByText("Thinking…")).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Message" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
  });

  it("shows the no-key message with a Keys button", () => {
    const onOpenKeys = vi.fn();
    render(<Chat {...base} noKey error="Add a key for Claude in Keys first." onOpenKeys={onOpenKeys} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Add a key for Claude in Keys first.");
    fireEvent.click(screen.getByRole("button", { name: "Open Keys" }));
    expect(onOpenKeys).toHaveBeenCalled();
  });
});

// What every page leans on the shared pieces for, said once: a busy button, a field's error, asking before a delete.
import { describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { Button } from "./Button";
import { ConfirmInline } from "./ConfirmInline";
import { Field } from "./Field";
import { FileButton } from "./ActionLink";

describe("Button", () => {
  it("never submits by accident, says when it's busy or pressed, and a file button hands over the file", () => {
    const { rerender } = render(<Button>Go</Button>);
    expect(screen.getByRole("button", { name: "Go" })).toHaveAttribute("type", "button");

    // while busy: switched off, announced, and saying what it's doing
    rerender(<Button busy busyLabel="Saving…">Save</Button>);
    const b = screen.getByRole("button", { name: "Saving…" });
    expect(b).toBeDisabled();
    expect(b).toHaveAttribute("aria-busy", "true");
    rerender(<Button busy>Save</Button>);
    expect(screen.getByRole("button")).toHaveTextContent("Save…");   // no label: its words, then dots

    rerender(<Button pressed>Bloom</Button>);
    expect(screen.getByRole("button", { name: "Bloom" })).toHaveAttribute("aria-pressed", "true");
    cleanup();

    const onFile = vi.fn();
    const { container, rerender: again } = render(<FileButton onFile={onFile}>Bring in a folder</FileButton>);
    const input = container.querySelector("input")!;
    const f = new File(["x"], "me.zip");
    fireEvent.change(input, { target: { files: [f] } });
    expect(onFile).toHaveBeenCalledWith(f);
    again(<FileButton onFile={onFile} busy busyLabel="Bringing it in…">Bring in a folder</FileButton>);
    expect(screen.getByText("Bringing it in…")).toBeInTheDocument();
    expect(input).toBeDisabled();
  });
});

describe("Field", () => {
  it("ties its label, hint and error to the input, and without an error announces nothing", () => {
    const { rerender } = render(<Field id="pw" label="Password" hint="At least ten letters." error="Too short.">
      <input />
    </Field>);
    const input = screen.getByLabelText("Password");
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveAccessibleDescription("At least ten letters. Too short.");
    expect(screen.getByRole("alert")).toHaveTextContent("Too short.");

    rerender(<Field id="pw" label="Password"><input /></Field>);
    expect(screen.getByLabelText("Password")).not.toHaveAttribute("aria-invalid");
    expect(screen.queryByRole("alert")).toBeNull();
  });
});

describe("ConfirmInline", () => {
  it("puts focus on the way back, or on its field, and confirms only once allowed", () => {
    const onConfirm = vi.fn(), onKeep = vi.fn();
    render(<ConfirmInline question="Delete it?" confirm="Delete it" onConfirm={onConfirm} onKeep={onKeep} />);
    expect(screen.getByRole("button", { name: "Keep it" })).toHaveFocus();   // Enter never deletes by accident
    fireEvent.click(screen.getByRole("button", { name: "Delete it" }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
    cleanup();

    const onAccount = vi.fn();
    const { rerender } = render(<ConfirmInline question="Delete your account?" confirm="Delete everything" canConfirm={false}
      onConfirm={onAccount} onKeep={() => {}} field={<input aria-label="Your password" />} />);
    const box = screen.getByLabelText("Your password");
    expect(box).toHaveFocus();
    fireEvent.submit(box.closest("form")!);
    expect(onAccount).not.toHaveBeenCalled();
    rerender(<ConfirmInline question="Delete your account?" confirm="Delete everything" canConfirm
      onConfirm={onAccount} onKeep={() => {}} field={<input aria-label="Your password" />} />);
    fireEvent.submit(box.closest("form")!);
    expect(onAccount).toHaveBeenCalledTimes(1);
  });
});

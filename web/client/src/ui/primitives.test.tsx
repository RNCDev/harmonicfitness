// What every page leans on the shared pieces for, said once: a busy button, a field's error, asking before a delete,
// the level cards, a section and a page's header.
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { Button } from "./Button";
import { ConfirmInline } from "./ConfirmInline";
import { Field } from "./Field";
import { FileButton, LinkButton } from "./ActionLink";
import { LevelCards } from "./LevelCards";
import { PageHeader } from "./PageHeader";
import { Section } from "./Section";

describe("Button", () => {
  it("is a plain button unless it says otherwise, and never submits a form by accident", () => {
    render(<Button>Go</Button>);
    expect(screen.getByRole("button", { name: "Go" })).toHaveAttribute("type", "button");
  });

  it("while busy: switched off, announced, and saying what it's doing", () => {
    const { rerender } = render(<Button busy busyLabel="Saving…">Save</Button>);
    const b = screen.getByRole("button", { name: "Saving…" });
    expect(b).toBeDisabled();
    expect(b).toHaveAttribute("aria-busy", "true");
    rerender(<Button busy>Save</Button>);
    expect(screen.getByRole("button")).toHaveTextContent("Save…");   // no label: its words, then dots
  });

  it("a toggle says whether it's on", () => {
    render(<Button pressed>Bloom</Button>);
    expect(screen.getByRole("button", { name: "Bloom" })).toHaveAttribute("aria-pressed", "true");
  });
});

describe("Field", () => {
  it("ties its label, hint and error to the input", () => {
    render(<Field id="pw" label="Password" hint="At least ten letters." error="Too short.">
      <input />
    </Field>);
    const input = screen.getByLabelText("Password");
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveAccessibleDescription("At least ten letters. Too short.");
    expect(screen.getByRole("alert")).toHaveTextContent("Too short.");
  });

  it("without an error, the input is valid and nothing is announced", () => {
    render(<Field id="pw" label="Password"><input /></Field>);
    expect(screen.getByLabelText("Password")).not.toHaveAttribute("aria-invalid");
    expect(screen.queryByRole("alert")).toBeNull();
  });
});

describe("ConfirmInline", () => {
  it("puts focus on the way back, so Enter never deletes by accident", () => {
    const onConfirm = vi.fn(), onKeep = vi.fn();
    render(<ConfirmInline question="Delete it?" confirm="Delete it" onConfirm={onConfirm} onKeep={onKeep} />);
    expect(screen.getByRole("button", { name: "Keep it" })).toHaveFocus();
    fireEvent.click(screen.getByRole("button", { name: "Delete it" }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it("with a field: focus there, and it confirms only once allowed", () => {
    const onConfirm = vi.fn();
    const { rerender } = render(<ConfirmInline question="Delete your account?" confirm="Delete everything" canConfirm={false}
      onConfirm={onConfirm} onKeep={() => {}} field={<input aria-label="Your password" />} />);
    const box = screen.getByLabelText("Your password");
    expect(box).toHaveFocus();
    fireEvent.submit(box.closest("form")!);
    expect(onConfirm).not.toHaveBeenCalled();
    rerender(<ConfirmInline question="Delete your account?" confirm="Delete everything" canConfirm
      onConfirm={onConfirm} onKeep={() => {}} field={<input aria-label="Your password" />} />);
    fireEvent.submit(box.closest("form")!);
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });
});

describe("the other shared pieces", () => {
  it("LevelCards: one radio per level, the chosen one checked", () => {
    const onChoose = vi.fn();
    render(<><p id="q">Which sounds like you?</p><LevelCards labelledBy="q" value="novice" onChoose={onChoose}
      choices={[{ level: "novice", said: "New to this." }, { level: "experienced", said: "Trained before." }]} /></>);
    expect(screen.getByRole("radiogroup", { name: "Which sounds like you?" })).toBeInTheDocument();
    expect(screen.getAllByRole("radio")[0]).toHaveAttribute("aria-checked", "true");
    fireEvent.click(screen.getAllByRole("radio")[1]);
    expect(onChoose).toHaveBeenCalledWith("experienced");
  });

  it("Section: a region named by its heading", () => {
    render(<Section id="cx-level" title="Your level"><p>Cards</p></Section>);
    expect(screen.getByRole("region", { name: "Your level" })).toHaveAttribute("id", "cx-level");
  });

  it("PageHeader: focus starts on the title, and Close is named by its word", () => {
    const onClose = vi.fn();
    render(<PageHeader id="t" title="Logs" onClose={onClose} />);
    expect(screen.getByRole("heading", { name: "Logs" })).toHaveFocus();
    fireEvent.click(screen.getByRole("button", { name: /^Close/ }));
    expect(onClose).toHaveBeenCalled();
  });

  it("FileButton: hands over the file chosen, and is switched off while busy", () => {
    const onFile = vi.fn();
    const { container, rerender } = render(<FileButton onFile={onFile}>Bring in a folder</FileButton>);
    const input = container.querySelector("input")!;
    const f = new File(["x"], "me.zip");
    fireEvent.change(input, { target: { files: [f] } });
    expect(onFile).toHaveBeenCalledWith(f);
    rerender(<FileButton onFile={onFile} busy busyLabel="Bringing it in…">Bring in a folder</FileButton>);
    expect(screen.getByText("Bringing it in…")).toBeInTheDocument();
    expect(input).toBeDisabled();
  });

  it("LinkButton: a real link", () => {
    render(<LinkButton href="/api/export" download>Download your files</LinkButton>);
    expect(screen.getByRole("link", { name: "Download your files" })).toHaveAttribute("href", "/api/export");
  });
});

import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { Question } from "./Question";
import type { OpenQuestion } from "../api";

const ASK: OpenQuestion = {
  tool_call_id: "tc1",
  questions: [
    { id: "feel", prompt: "How do you feel today?", multi: false, other: true, options: [
      { label: "Fresh" }, { label: "Okay", recommended: true, description: "A normal day" }, { label: "Tired" },
    ] },
    { id: "areas", prompt: "Anything sore?", multi: true, other: false, options: [
      { label: "Knees" }, { label: "Back" },
    ] },
  ],
};

describe("the check-in question", () => {
  it("preselects the recommended option", () => {
    render(<Question ask={ASK} onSend={() => {}} />);
    expect(screen.getByRole("radio", { name: /Okay/ })).toBeChecked();
    expect(screen.getByText("Recommended")).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "How do you feel today?" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Other" })).toBeInTheDocument();
  });

  it("sends every question's answer once", () => {
    const onSend = vi.fn();
    render(<Question ask={ASK} onSend={onSend} />);
    fireEvent.click(screen.getByRole("radio", { name: /Tired/ }));
    fireEvent.click(screen.getByRole("checkbox", { name: "Knees" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "Back" }));
    const send = screen.getByRole("button", { name: "Send" });
    fireEvent.click(send);
    fireEvent.click(send);
    expect(onSend).toHaveBeenCalledTimes(1);
    expect(onSend).toHaveBeenCalledWith("tc1", { feel: ["Tired"], areas: ["Knees", "Back"] });
    expect(send).toBeDisabled();
  });

  it("sends the Other text as the answer when typed", () => {
    const onSend = vi.fn();
    render(<Question ask={ASK} onSend={onSend} />);
    fireEvent.change(screen.getByRole("textbox", { name: "Other" }), { target: { value: " wiped out " } });
    fireEvent.click(screen.getByRole("checkbox", { name: "Back" }));
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(onSend).toHaveBeenCalledWith("tc1", { feel: "other: wiped out", areas: ["Back"] });
  });

  it("will not send while a question has no answer", () => {
    render(<Question ask={ASK} onSend={() => {}} />);
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
  });
});

describe("a refused answer", () => {
  it("opens the form again so it can be sent once more", async () => {
    const onSend = vi.fn().mockResolvedValueOnce(false).mockResolvedValueOnce(true);
    render(<Question ask={ASK} onSend={onSend} />);
    fireEvent.click(screen.getByRole("radio", { name: /Tired/ }));
    fireEvent.click(screen.getByRole("checkbox", { name: "Knees" }));
    const send = screen.getByRole("button", { name: "Send" });
    fireEvent.click(send);
    await waitFor(() => expect(send).toBeEnabled());
    fireEvent.click(send);
    await waitFor(() => expect(onSend).toHaveBeenCalledTimes(2));
  });

  it("locks the options while Other has text", () => {
    render(<Question ask={ASK} onSend={() => {}} />);
    fireEvent.change(screen.getByRole("textbox", { name: "Other" }), { target: { value: "x" } });
    expect(screen.getByRole("radio", { name: /Tired/ })).toBeDisabled();
  });
});

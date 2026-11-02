import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ContextColumn } from "./ContextColumn";

vi.mock("./KeysBox", () => ({ KeysBox: () => null }));

describe("Settings", () => {
  it("holds keys, not coaches (they have their own page)", () => {
    render(<ContextColumn username="sam" open onClose={vi.fn()} onSignedOut={vi.fn()} onSignOut={vi.fn()} />);
    expect(screen.queryByRole("heading", { name: "Coaches" })).toBeNull();
  });

  it("credits the backgrounds to Book of Shapes", () => {
    render(<ContextColumn username="sam" open onClose={vi.fn()} onSignedOut={vi.fn()} onSignOut={vi.fn()} onSky={vi.fn()} />);
    const link = screen.getByRole("link", { name: "Book of Shapes" });
    expect(link).toHaveAttribute("href", "https://bookofshapes.com");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
    expect(link.closest("p")).toHaveTextContent("Nikolaj Sokolowski");
    expect(screen.queryByRole("button", { name: /Arcs/ })).toBeNull();   // retired: its licence asks it not be published
    expect(screen.getByRole("button", { name: /Bloom/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Lissajous/ })).toBeNull();   // replaced in 0.50.3
    expect(screen.queryByRole("button", { name: /Hex Strands/ })).toBeNull();   // replaced by Woven Grid in 0.50.4
    expect(screen.getByRole("button", { name: /Woven Grid/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Node Garden/ })).toBeInTheDocument();
  });
});

describe("the version", () => {
  it("shows at the foot of Settings", () => {
    render(<ContextColumn username="sam" version="0.42.3 (abc1234)" open onClose={vi.fn()}
      onSignedOut={vi.fn()} onSignOut={vi.fn()} />);
    expect(screen.getByText("Version 0.42.3 (abc1234)")).toBeInTheDocument();
  });
});

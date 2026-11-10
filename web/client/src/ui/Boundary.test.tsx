import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { Boundary } from "./Boundary";

function Broken(): never {
  throw new Error("a shape the page didn't expect");
}

// React and the boundary both say a caught error on the console: kept quiet here
afterEach(() => vi.restoreAllMocks());
const hush = () => vi.spyOn(console, "error").mockImplementation(() => {});

describe("the boundary", () => {
  it("draws its children while nothing breaks", () => {
    render(<Boundary what="The Logs page"><p>Fine</p></Boundary>);
    expect(screen.getByText("Fine")).toBeInTheDocument();
  });

  it("says what broke and offers a reload, leaving the pages beside it alone", () => {
    hush();
    render(<>
      <Boundary what="The Logs page"><Broken /></Boundary>
      <Boundary what="The chat"><p>Still here</p></Boundary>
    </>);
    expect(screen.getByRole("alert")).toHaveTextContent("The Logs page hit a problem it couldn't draw.");
    expect(screen.getByRole("button", { name: "Reload the page" })).toBeInTheDocument();
    expect(screen.getByText("Still here")).toBeInTheDocument();
  });

  it("around the whole app, it fills the page with the sky, the words and the reload", () => {
    hush();
    render(<Boundary><Broken /></Boundary>);
    expect(screen.getByRole("heading", { name: "Something went wrong" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reload the page" })).toBeInTheDocument();
  });
});

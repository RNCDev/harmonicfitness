import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createRef } from "react";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { AudioPlayer, type AudioHandle } from "./Player";

// jsdom's media elements neither play nor pause: these stand in, saying so the way a browser would.
let play: ReturnType<typeof vi.spyOn>, pause: ReturnType<typeof vi.spyOn>;
beforeEach(() => {
  play = vi.spyOn(HTMLMediaElement.prototype, "play").mockImplementation(function (this: HTMLMediaElement) {
    Object.defineProperty(this, "paused", { value: false, configurable: true });
    this.dispatchEvent(new Event("play"));
    return Promise.resolve();
  });
  pause = vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(function (this: HTMLMediaElement) {
    Object.defineProperty(this, "paused", { value: true, configurable: true });
    this.dispatchEvent(new Event("pause"));
  });
});
afterEach(() => vi.restoreAllMocks());

const button = (name: string) => screen.getByRole("button", { name });

describe("the audio player", () => {
  it("plays one clip at a time across the page: starting one pauses the other", () => {
    const { container } = render(<><AudioPlayer src="/a.mp3" label="Nora's sample" /><AudioPlayer src="/b.mp3" label="Leah's sample" /></>);
    const [nora, leah] = container.querySelectorAll("audio");
    fireEvent.click(button("Play Nora's sample"));
    pause.mockClear();
    expect(button("Pause Nora's sample")).toBeInTheDocument();
    fireEvent.click(button("Play Leah's sample"));
    expect(button("Play Nora's sample")).toBeInTheDocument();   // paused by Leah's
    expect(button("Pause Leah's sample")).toBeInTheDocument();
    expect(play.mock.contexts).toEqual([nora, leah]);
    expect(pause.mock.contexts).toEqual([nora]);
    fireEvent.click(button("Pause Leah's sample"));
    expect(button("Play Leah's sample")).toBeInTheDocument();
  });

  it("lazy: fetches nothing until the first play, then sets the clip once", () => {
    const { container } = render(<AudioPlayer src="/demo.mp3" label="Jo's workout" lazy />);
    const audio = container.querySelector("audio")!;
    expect(audio).not.toHaveAttribute("src");
    expect(audio).toHaveAttribute("preload", "none");
    fireEvent.click(button("Play Jo's workout"));
    expect(audio.getAttribute("src")).toBe("/demo.mp3");
    fireEvent.click(button("Pause Jo's workout"));
    fireEvent.click(button("Play Jo's workout"));
    expect(audio.getAttribute("src")).toBe("/demo.mp3");
    expect(play.mock.contexts).toEqual([audio, audio]);
  });

  it("a new clip stops the last one and starts from nothing", () => {
    const onPlaying = vi.fn();
    const { container, rerender } = render(<AudioPlayer src="/one.mp3" label="Jo's workout" lazy onPlaying={onPlaying} />);
    fireEvent.click(button("Play Jo's workout"));
    expect(onPlaying).toHaveBeenLastCalledWith(true);
    pause.mockClear();
    rerender(<AudioPlayer src="/two.mp3" label="Jo's workout" lazy onPlaying={onPlaying} />);
    expect(pause.mock.contexts).toEqual([container.querySelector("audio")]);
    expect(onPlaying).toHaveBeenLastCalledWith(false);
    expect(button("Play Jo's workout")).toBeInTheDocument();
    expect(container.querySelector("audio")).not.toHaveAttribute("src");   // the last clip let go, the next not yet fetched
    expect(screen.getByRole("slider", { name: "Jo's workout, position" })).toBeDisabled();   // its length unknown again
  });

  it("shows the time once the length is known, and seeks along it", () => {
    const { container } = render(<AudioPlayer src="/a.mp3" label="Nora's sample" idle="45 s" />);
    expect(screen.getByText("45 s")).toBeInTheDocument();
    const audio = container.querySelector("audio")!;
    Object.defineProperty(audio, "duration", { value: 45, configurable: true });
    fireEvent(audio, new Event("loadedmetadata"));
    expect(screen.getByText("0:45")).toBeInTheDocument();
    const seek = screen.getByRole("slider", { name: "Nora's sample, position" });
    fireEvent.change(seek, { target: { value: "12" } });
    expect(audio.currentTime).toBe(12);
    expect(screen.getByText("0:12 / 0:45")).toBeInTheDocument();
  });

  it("plays from a moment when asked, once the clip's length is known", () => {
    const ref = createRef<AudioHandle>();
    const { container } = render(<AudioPlayer ref={ref} src="/demo.mp3" label="Jo's workout" lazy />);
    const audio = container.querySelector("audio")!;
    act(() => ref.current!.play(56));
    expect(play).not.toHaveBeenCalled();   // waits for the clip's metadata
    expect(audio.getAttribute("src")).toBe("/demo.mp3");
    fireEvent(audio, new Event("loadedmetadata"));
    expect(audio.currentTime).toBe(56);
    expect(play).toHaveBeenCalledTimes(1);
  });
});

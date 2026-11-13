import React from "react";
import { cleanup, fireEvent, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { FloatyInteractions, springFrames } from "./FloatyInteractions";

type AnimateCall = {
  element: HTMLElement;
  keyframes: Keyframe[];
  cancel: ReturnType<typeof vi.fn>;
};

function parseTranslate(raw: unknown): { x: number; y: number } | null {
  if (typeof raw !== "string") return null;
  const match = /^(-?\d+(?:\.\d+)?)px (-?\d+(?:\.\d+)?)px$/.exec(raw);
  if (!match) return null;
  return { x: Number(match[1]), y: Number(match[2]) };
}

function firstNonZero(frames: Keyframe[]) {
  for (const frame of frames) {
    const point = parseTranslate(frame.translate);
    if (point && (point.x !== 0 || point.y !== 0)) return point;
  }
  return null;
}

function stubRect(element: HTMLElement, rect: Partial<DOMRect>) {
  Object.defineProperty(element, "getBoundingClientRect", {
    configurable: true,
    value: () => ({
      x: rect.left ?? 0,
      y: rect.top ?? 0,
      left: rect.left ?? 0,
      top: rect.top ?? 0,
      right: (rect.left ?? 0) + (rect.width ?? 0),
      bottom: (rect.top ?? 0) + (rect.height ?? 0),
      width: rect.width ?? 0,
      height: rect.height ?? 0,
      toJSON() {
        return this;
      },
    }),
  });
}

describe("FloatyInteractions", () => {
  const calls: AnimateCall[] = [];
  let reduced = false;
  let changeHandler: ((event: MediaQueryListEvent) => void) | null = null;
  const supports = vi.fn(() => true);

  beforeEach(() => {
    calls.length = 0;
    reduced = false;
    changeHandler = null;
    supports.mockReturnValue(true);

    if (typeof PointerEvent === "undefined") {
      class PointerEventPolyfill extends MouseEvent {
        pointerId: number;
        isPrimary: boolean;
        constructor(type: string, init: MouseEventInit & { pointerId?: number; isPrimary?: boolean } = {}) {
          super(type, init);
          this.pointerId = init.pointerId ?? 1;
          this.isPrimary = init.isPrimary ?? true;
        }
      }
      Object.defineProperty(globalThis, "PointerEvent", {
        configurable: true,
        writable: true,
        value: PointerEventPolyfill,
      });
    }

    Object.defineProperty(window, "matchMedia", {
      configurable: true,
      writable: true,
      value: vi.fn((query: string) => ({
        get matches() {
          return reduced;
        },
        media: query,
        addEventListener: (_type: string, listener: (event: MediaQueryListEvent) => void) => {
          changeHandler = listener;
        },
        removeEventListener: () => {
          changeHandler = null;
        },
        addListener: () => undefined,
        removeListener: () => undefined,
        dispatchEvent: () => false,
        onchange: null,
      })),
    });

    Object.defineProperty(globalThis, "CSS", {
      configurable: true,
      writable: true,
      value: { supports },
    });

    Element.prototype.animate = vi.fn(function animate(
      this: HTMLElement,
      keyframes: Keyframe[] | PropertyIndexedKeyframes,
    ) {
      const cancel = vi.fn();
      const animation = {
        cancel,
        onfinish: null as ((this: Animation, ev: AnimationPlaybackEvent) => void) | null,
        oncancel: null as ((this: Animation, ev: AnimationPlaybackEvent) => void) | null,
      };
      calls.push({
        element: this,
        keyframes: Array.isArray(keyframes) ? keyframes : [],
        cancel,
      });
      return animation as unknown as Animation;
    });
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  function mountWith(ui: React.ReactNode) {
    return render(
      <>
        <FloatyInteractions />
        {ui}
      </>,
    );
  }

  function press(element: HTMLElement, clientX: number, clientY: number) {
    element.dispatchEvent(
      new PointerEvent("pointerdown", {
        bubbles: true,
        cancelable: true,
        button: 0,
        clientX,
        clientY,
        isPrimary: true,
        pointerId: 1,
      }),
    );
  }

  it("nudges left for a right-edge press", () => {
    const { getByRole } = mountWith(<button type="button">Go</button>);
    const button = getByRole("button");
    stubRect(button, { left: 0, top: 0, width: 100, height: 40 });
    press(button, 95, 20);
    const point = firstNonZero(calls[0]!.keyframes);
    expect(point?.x).toBeLessThan(0);
  });

  it("nudges right for a left-edge press", () => {
    const { getByRole } = mountWith(<button type="button">Go</button>);
    const button = getByRole("button");
    stubRect(button, { left: 0, top: 0, width: 100, height: 40 });
    press(button, 5, 20);
    const point = firstNonZero(calls[0]!.keyframes);
    expect(point?.x).toBeGreaterThan(0);
  });

  it("nudges down for a top-edge press", () => {
    const { getByRole } = mountWith(<button type="button">Go</button>);
    const button = getByRole("button");
    stubRect(button, { left: 0, top: 0, width: 100, height: 40 });
    press(button, 50, 2);
    const point = firstNonZero(calls[0]!.keyframes);
    expect(point?.y).toBeGreaterThan(0);
  });

  it("uses a tiny downward tap for a center press", () => {
    const { getByRole } = mountWith(<button type="button">Go</button>);
    const button = getByRole("button");
    stubRect(button, { left: 0, top: 0, width: 100, height: 40 });
    press(button, 50, 20);
    const point = firstNonZero(calls[0]!.keyframes);
    expect(point?.x).toBe(0);
    expect(point?.y).toBeGreaterThan(0);
  });

  it("does not animate disabled or aria-disabled controls", () => {
    const { getByRole } = mountWith(
      <>
        <button type="button" disabled>
          Off
        </button>
        <button type="button" aria-disabled="true">
          Soft
        </button>
      </>,
    );
    for (const button of [getByRole("button", { name: "Off" }), getByRole("button", { name: "Soft" })]) {
      stubRect(button, { left: 0, top: 0, width: 80, height: 32 });
      press(button, 40, 16);
    }
    expect(calls).toHaveLength(0);
  });

  it("leaves inputs and range sliders untouched", () => {
    const { container } = mountWith(
      <>
        <input aria-label="Name" />
        <input type="range" aria-label="Volume" min={0} max={10} />
      </>,
    );
    const text = container.querySelector('input[aria-label="Name"]') as HTMLInputElement;
    const range = container.querySelector('input[type="range"]') as HTMLInputElement;
    stubRect(text, { left: 0, top: 0, width: 120, height: 32 });
    stubRect(range, { left: 0, top: 40, width: 120, height: 24 });
    press(text, 20, 16);
    press(range, 60, 52);
    expect(calls).toHaveLength(0);
  });

  it("respects data-floaty=off ancestors", () => {
    const { getByRole } = mountWith(
      <div data-floaty="off">
        <button type="button">Fixed</button>
      </div>,
    );
    const button = getByRole("button");
    stubRect(button, { left: 0, top: 0, width: 80, height: 32 });
    press(button, 40, 16);
    expect(calls).toHaveLength(0);
  });

  it("animates once for Enter and Space on a focused button", () => {
    const onClick = vi.fn();
    const { getByRole } = mountWith(
      <button type="button" onClick={onClick}>
        Act
      </button>,
    );
    const button = getByRole("button");
    button.focus();
    fireEvent.keyDown(button, { key: "Enter" });
    fireEvent.keyDown(button, { key: " " });
    expect(calls).toHaveLength(2);
    fireEvent.click(button);
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("ignores keyboard auto-repeat", () => {
    const { getByRole } = mountWith(<button type="button">Act</button>);
    const button = getByRole("button");
    button.focus();
    fireEvent.keyDown(button, { key: "Enter", repeat: true });
    expect(calls).toHaveLength(0);
  });

  it("does not animate Space on a link", () => {
    const { getByRole } = mountWith(<a href="/search">Players</a>);
    const link = getByRole("link");
    link.focus();
    fireEvent.keyDown(link, { key: " " });
    expect(calls).toHaveLength(0);
  });

  it("starts no animation when reduced motion is already preferred", () => {
    reduced = true;
    const { getByRole } = mountWith(<button type="button">Go</button>);
    const button = getByRole("button");
    stubRect(button, { left: 0, top: 0, width: 100, height: 40 });
    fireEvent.pointerDown(button, { button: 0, clientX: 95, clientY: 20, isPrimary: true });
    expect(calls).toHaveLength(0);
  });

  it("cancels active motion when reduced motion turns on", () => {
    const { getByRole } = mountWith(<button type="button">Go</button>);
    const button = getByRole("button");
    stubRect(button, { left: 0, top: 0, width: 100, height: 40 });
    press(button, 95, 20);
    expect(calls).toHaveLength(1);
    reduced = true;
    changeHandler?.({ matches: true } as MediaQueryListEvent);
    expect(calls[0]!.cancel).toHaveBeenCalled();
  });

  it("cancels the previous animation on rapid repeats", () => {
    const { getByRole } = mountWith(<button type="button">Go</button>);
    const button = getByRole("button");
    stubRect(button, { left: 0, top: 0, width: 100, height: 40 });
    press(button, 95, 20);
    press(button, 5, 20);
    expect(calls).toHaveLength(2);
    expect(calls[0]!.cancel).toHaveBeenCalled();
  });

  it("cleans up listeners and animations on unmount", () => {
    const { getByRole, unmount } = mountWith(<button type="button">Go</button>);
    const button = getByRole("button");
    stubRect(button, { left: 0, top: 0, width: 100, height: 40 });
    press(button, 95, 20);
    unmount();
    expect(calls[0]!.cancel).toHaveBeenCalled();
    const after = calls.length;
    press(button, 95, 20);
    expect(calls).toHaveLength(after);
  });

  it("stays quiet when Element.animate is missing", () => {
    // @ts-expect-error intentional unsupported path
    Element.prototype.animate = undefined;
    const onClick = vi.fn();
    const { getByRole } = mountWith(
      <button type="button" onClick={onClick}>
        Go
      </button>,
    );
    const button = getByRole("button");
    stubRect(button, { left: 0, top: 0, width: 100, height: 40 });
    expect(() => press(button, 95, 20)).not.toThrow();
    fireEvent.click(button);
    expect(onClick).toHaveBeenCalledTimes(1);
    expect(calls).toHaveLength(0);
  });

  it("ends spring samples at exactly 0px 0px", () => {
    const frames = springFrames(82, -40);
    expect(frames.at(-1)?.translate).toBe("0px 0px");
    expect(frames.at(-1)?.offset).toBe(1);
  });
});

"use client";

import { useEffect } from "react";

/**
 * Local design experiment: tiny, click-position-aware spring reactions.
 * Event-delegated, idle-cost near zero; no wrappers or per-frame React state.
 * Animates independent CSS `translate` so authored `transform` rules stay intact.
 */
const INTERACTIVE = 'button, a[href], summary, [data-floaty="on"]';
const DURATION_MS = 560;
const STEPS = 34;
const STIFFNESS = 270;
const DAMPING = 20;
const EDGE_IMPULSE = 82;
const CENTER_IMPULSE = 42;

function clamp(n: number, min: number, max: number) {
  return Math.max(min, Math.min(max, n));
}

/** Exported for unit tests of the spring sample path. */
export function springFrames(vx0: number, vy0: number): Keyframe[] {
  const dt = DURATION_MS / 1000 / STEPS;
  let x = 0;
  let y = 0;
  let vx = vx0;
  let vy = vy0;
  const frames: Keyframe[] = [];
  for (let i = 0; i <= STEPS; i++) {
    frames.push({
      offset: i / STEPS,
      translate: `${x.toFixed(3)}px ${y.toFixed(3)}px`,
    });
    vx += (-STIFFNESS * x - DAMPING * vx) * dt;
    vy += (-STIFFNESS * y - DAMPING * vy) * dt;
    x += vx * dt;
    y += vy * dt;
  }
  frames[frames.length - 1] = { offset: 1, translate: "0px 0px" };
  return frames;
}

function interactiveTarget(target: EventTarget | null): HTMLElement | null {
  if (!(target instanceof Element)) return null;
  const element = target.closest(INTERACTIVE);
  if (!(element instanceof HTMLElement)) return null;
  if (!element.isConnected) return null;
  if (element.closest('[data-floaty="off"]')) return null;
  if (element.matches(':disabled, [aria-disabled="true"]')) return null;
  if (element.closest("fieldset")?.disabled) return null;
  return element;
}

function canAnimate(element: HTMLElement): boolean {
  if (typeof element.animate !== "function") return false;
  if (typeof CSS !== "undefined" && typeof CSS.supports === "function") {
    if (!CSS.supports("translate", "1px 1px")) return false;
  }
  return true;
}

export function FloatyInteractions() {
  useEffect(() => {
    const motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    const active = new Map<HTMLElement, Animation>();

    function clearAll() {
      for (const animation of active.values()) animation.cancel();
      active.clear();
    }

    function kick(element: HTMLElement, velocityX: number, velocityY: number) {
      if (motionQuery.matches || !canAnimate(element)) return;
      active.get(element)?.cancel();
      const frames = springFrames(velocityX, velocityY);
      const animation = element.animate(frames, {
        duration: DURATION_MS,
        easing: "linear",
      });
      active.set(element, animation);
      const release = () => {
        if (active.get(element) === animation) active.delete(element);
      };
      animation.onfinish = release;
      animation.oncancel = release;
    }

    function onPointerDown(event: PointerEvent) {
      // jsdom/testing-library may omit button/isPrimary; treat missing as primary left-click.
      if ((event.button ?? 0) !== 0 || event.isPrimary === false) return;
      const element = interactiveTarget(event.target);
      if (!element) return;
      const rect = element.getBoundingClientRect();
      if (!rect.width || !rect.height) return;

      const nx = clamp(
        (rect.left + rect.width / 2 - event.clientX) / (rect.width / 2),
        -1,
        1,
      );
      const ny = clamp(
        (rect.top + rect.height / 2 - event.clientY) / (rect.height / 2),
        -1,
        1,
      );
      if (Math.hypot(nx, ny) < 0.16) kick(element, 0, CENTER_IMPULSE);
      else kick(element, nx * EDGE_IMPULSE, ny * EDGE_IMPULSE);
    }

    function onKeyDown(event: KeyboardEvent) {
      if (event.repeat || (event.key !== "Enter" && event.key !== " ")) return;
      const element = interactiveTarget(event.target);
      if (!element) return;
      // Keep Space on links as native scroll; do not synthesize clicks.
      if (element.tagName === "A" && event.key === " ") return;
      kick(element, 0, CENTER_IMPULSE);
    }

    function onMotionPreferenceChange() {
      if (motionQuery.matches) clearAll();
    }

    document.addEventListener("pointerdown", onPointerDown, {
      capture: true,
      passive: true,
    });
    document.addEventListener("keydown", onKeyDown, true);
    motionQuery.addEventListener("change", onMotionPreferenceChange);

    return () => {
      document.removeEventListener("pointerdown", onPointerDown, true);
      document.removeEventListener("keydown", onKeyDown, true);
      motionQuery.removeEventListener("change", onMotionPreferenceChange);
      clearAll();
    };
  }, []);

  return null;
}

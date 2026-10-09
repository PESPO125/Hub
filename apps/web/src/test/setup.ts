import "@testing-library/jest-dom/vitest";
import { transferableAbortController } from "node:util";

// Keep Request and AbortSignal in the same Node realm when React Router creates
// navigation requests inside jsdom.
const nodeAbortController = transferableAbortController();
globalThis.AbortController = nodeAbortController.constructor as typeof AbortController;
globalThis.AbortSignal = nodeAbortController.signal.constructor as typeof AbortSignal;

// jsdom no implementa <dialog>.showModal
if (!HTMLDialogElement.prototype.showModal) {
  HTMLDialogElement.prototype.showModal = function () { this.setAttribute("open", ""); };
  HTMLDialogElement.prototype.close = function () { this.removeAttribute("open"); this.dispatchEvent(new Event("close")); };
}
if (!window.matchMedia) {
  window.matchMedia = (q: string) =>
    ({ matches: false, media: q, onchange: null, addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {}, dispatchEvent: () => false }) as MediaQueryList;
}

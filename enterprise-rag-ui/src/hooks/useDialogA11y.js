import { useRef, useEffect } from "react";

const FOCUSABLE =
  'button:not([disabled]), [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';

// Gives a dialog the keyboard behaviour it needs: Escape closes, Tab cycles
// inside it, and focus returns to whatever opened it. Returns the panel ref.
export function useDialogA11y(isOpen, onClose) {
  const panelRef = useRef(null);
  const returnRef = useRef(null);

  // Held in a ref so an inline callback from the caller cannot re-run the
  // effect on every render, which would keep yanking focus to the first item.
  const closeRef = useRef(onClose);
  useEffect(() => { closeRef.current = onClose; });

  useEffect(() => {
    if (!isOpen) return;

    returnRef.current = document.activeElement;
    const focusables = () => panelRef.current?.querySelectorAll(FOCUSABLE) ?? [];
    focusables()[0]?.focus();

    const onKeyDown = (e) => {
      if (e.key === "Escape") {
        closeRef.current();
        return;
      }
      if (e.key !== "Tab") return;
      const items = focusables();
      if (!items.length) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      returnRef.current?.focus?.();
    };
  }, [isOpen]);

  return panelRef;
}

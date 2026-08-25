import { useRef, useEffect } from "react";

// Calls onOutside when a pointer press lands outside ref, while active.
export function useOutsideClick(active, ref, onOutside) {
  const handlerRef = useRef(onOutside);
  useEffect(() => { handlerRef.current = onOutside; });

  useEffect(() => {
    if (!active) return;
    const onDown = (e) => {
      if (!ref.current?.contains(e.target)) handlerRef.current();
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [active, ref]);
}

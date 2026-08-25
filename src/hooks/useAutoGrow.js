import { useRef, useEffect } from "react";

// Grows a textarea with its content up to maxHeight, then lets it scroll.
export function useAutoGrow(value, maxHeight = 200) {
  const ref = useRef(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, maxHeight) + "px";
  }, [value, maxHeight]);

  return ref;
}

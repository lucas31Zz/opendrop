// Combo: a custom dropdown replacing the native <select>. WebView2's
// native option popup renders unstyleable OS chrome (light grey list)
// over the dark UI, so the menu is drawn in-app instead: a button in
// the recessed field language + an opaque popup list. Keyboard:
// Enter/Space/Arrows open, Arrows/Home/End move, Enter/Space choose,
// Esc/Tab close; click-outside closes. Accessible name = the current
// option text (stable for UIA Invoke), listbox/option roles exposed.
import { useEffect, useRef, useState } from "react";
import { ChevronDown } from "lucide-react";

type Props = {
  value: number;
  options: string[];
  onChange: (idx: number) => void;
  className?: string;
};

export default function Combo({ value, options, onChange, className }: Props) {
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(value);
  const [up, setUp] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);

  // Click outside closes the menu.
  useEffect(() => {
    if (!open) return;
    const onDown = (e: PointerEvent) => {
      if (!wrapRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", onDown);
    return () => document.removeEventListener("pointerdown", onDown);
  }, [open]);

  const openMenu = (from: "down" | "up") => {
    const el = wrapRef.current;
    if (el) {
      const r = el.getBoundingClientRect();
      // Flip upward when the combo sits near the bottom of a scroll
      // area, but only if there is room above it.
      setUp(from === "up" || (window.innerHeight - r.bottom < 190 && r.top > 190));
    }
    setActive(value);
    setOpen(true);
  };

  const choose = (idx: number) => {
    onChange(idx);
    setOpen(false);
  };

  const onKey = (e: React.KeyboardEvent) => {
    if (!open) {
      if (e.key === "ArrowDown" || e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        openMenu("down");
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        openMenu("up");
      }
      return;
    }
    if (e.key === "Escape") {
      e.preventDefault();
      // Stop here: the Settings window listens for a window-level
      // Escape and must not close when only the menu was dismissed.
      e.stopPropagation();
      setOpen(false);
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((a) => Math.min(a + 1, options.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => Math.max(a - 1, 0));
    } else if (e.key === "Home") {
      e.preventDefault();
      setActive(0);
    } else if (e.key === "End") {
      e.preventDefault();
      setActive(options.length - 1);
    } else if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      choose(active);
    } else if (e.key === "Tab") {
      setOpen(false);
    }
  };

  return (
    <div ref={wrapRef} className={`combo-wrap ${className ?? ""}`} onKeyDown={onKey}>
      <button
        type="button"
        className="combo"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-activedescendant={open ? `combo-opt-${active}` : undefined}
        onClick={() => (open ? setOpen(false) : openMenu("down"))}
      >
        <span className="combo-value">{options[value] ?? ""}</span>
        <ChevronDown size={14} aria-hidden className="combo-chev" />
      </button>
      {open ? (
        <div className={up ? "combo-menu up" : "combo-menu"} role="listbox">
          {options.map((label, i) => (
            <div
              key={label}
              id={`combo-opt-${i}`}
              role="option"
              aria-selected={i === value}
              className={
                "combo-option" +
                (i === active ? " active" : "") +
                (i === value ? " is-selected" : "")
              }
              onPointerDown={(e) => {
                e.preventDefault();
                choose(i);
              }}
              onPointerEnter={() => setActive(i)}
            >
              {label}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

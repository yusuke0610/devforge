import { useCallback, useEffect, useRef, useState, type Ref } from "react";

import styles from "./Combobox.module.css";

type ComboboxProps = {
  value: string;
  onChange: (value: string) => void;
  options: string[];
  placeholder?: string;
  allowCustom?: boolean;
  /** 内部 input への ref（バリデーション失敗時のフォーカス用） */
  inputRef?: Ref<HTMLInputElement>;
  /** バリデーション失敗フィールドとして強調するか（aria-invalid を付与） */
  invalid?: boolean;
};

/** 検索可能なプルダウンコンポーネント */
export function Combobox({
  value,
  onChange,
  options,
  placeholder,
  allowCustom = false,
  inputRef,
  invalid,
}: ComboboxProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState(value);
  const [activeIndex, setActiveIndex] = useState(-1);
  const containerRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  useEffect(() => {
    setQuery(value);
  }, [value]);

  const filtered = options.filter((opt) => opt.toLowerCase().includes(query.toLowerCase()));

  const select = useCallback(
    (val: string) => {
      onChange(val);
      setQuery(val);
      setOpen(false);
      setActiveIndex(-1);
    },
    [onChange],
  );

  const handleBlur = useCallback(() => {
    // blur後に少し待ってからリストクリックを許可する
    setTimeout(() => {
      if (!containerRef.current?.contains(document.activeElement)) {
        setOpen(false);
        if (!allowCustom && !options.includes(query)) {
          setQuery(value);
        } else if (query !== value) {
          onChange(query);
        }
      }
    }, 150);
  }, [allowCustom, onChange, options, query, value]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!open && (e.key === "ArrowDown" || e.key === "ArrowUp")) {
      setOpen(true);
      return;
    }

    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        setActiveIndex((prev) => (prev < filtered.length - 1 ? prev + 1 : prev));
        break;
      case "ArrowUp":
        e.preventDefault();
        setActiveIndex((prev) => (prev > 0 ? prev - 1 : prev));
        break;
      case "Enter":
        e.preventDefault();
        if (open && activeIndex >= 0 && activeIndex < filtered.length) {
          select(filtered[activeIndex]);
        }
        break;
      case "Escape":
        setOpen(false);
        setActiveIndex(-1);
        break;
    }
  };

  useEffect(() => {
    if (activeIndex >= 0 && listRef.current) {
      const item = listRef.current.children[activeIndex] as HTMLElement | undefined;
      item?.scrollIntoView({ block: "nearest" });
    }
  }, [activeIndex]);

  return (
    <div className={styles.container} ref={containerRef}>
      <input
        ref={inputRef}
        type="text"
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
          setActiveIndex(-1);
        }}
        onFocus={() => setOpen(true)}
        onBlur={handleBlur}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        role="combobox"
        aria-expanded={open}
        aria-autocomplete="list"
        aria-invalid={invalid || undefined}
      />
      {open && filtered.length > 0 && (
        <ul className={styles.dropdown} ref={listRef} role="listbox">
          {filtered.map((opt, i) => (
            <li
              key={opt}
              className={`${styles.option} ${i === activeIndex ? styles.active : ""}`}
              onMouseDown={(e) => {
                e.preventDefault();
                select(opt);
              }}
              role="option"
              aria-selected={i === activeIndex}
            >
              {opt}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

"use client";

import { useEffect, useId, useRef, useState } from "react";
import type { EntityPublic } from "@/lib/api/contracts";

/** Nonmodal WAI-ARIA combobox. Focus stays on the input; nothing hides the page. */
export function LiveEntityCombobox({
  query,
  type,
  selected,
  choices,
  disabled,
  unavailable,
  onQuery,
  onSelect,
}: {
  query: string;
  type: "artist" | "movie";
  selected: EntityPublic | null;
  choices: EntityPublic[];
  disabled: boolean;
  unavailable: boolean;
  onQuery: (value: string) => void;
  onSelect: (entity: EntityPublic) => void;
}) {
  const id = useId();
  const input = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const visible = open && !unavailable && !disabled && choices.length > 0;
  const listId = `${id}-options`;
  const optionId = (index: number) => `${id}-option-${choices[index]?.id}`;
  useEffect(() => {
    setActive(-1);
  }, [choices]);
  useEffect(() => {
    if (unavailable || selected || disabled) setOpen(false);
  }, [unavailable, selected, disabled]);
  useEffect(() => {
    if (visible && active >= 0)
      document
        .getElementById(optionId(active))
        ?.scrollIntoView({ block: "nearest" });
    // Only the active visible option is scrolled; list IDs are stable for this mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, visible]);

  function select(entity: EntityPublic) {
    setOpen(false);
    setActive(-1);
    onSelect(entity);
  }
  return (
    <div
      className="seed-combobox live-seed-combobox"
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) {
          setOpen(false);
          setActive(-1);
        }
      }}
    >
      <label id={`${id}-label`} className="seed-label" htmlFor={`${id}-input`}>
        Choose your favourite
      </label>
      <div className="seed-search-row">
        <svg
          width="21"
          height="21"
          viewBox="0 0 24 24"
          fill="none"
          aria-hidden="true"
        >
          <circle
            cx="10.5"
            cy="10.5"
            r="6.5"
            stroke="currentColor"
            strokeWidth="1.8"
          />
          <path d="m16 16 4.5 4.5" stroke="currentColor" strokeWidth="1.8" />
        </svg>
        <input
          ref={input}
          id={`${id}-input`}
          className="seed-input"
          role="combobox"
          type="text"
          aria-autocomplete="list"
          aria-expanded={visible}
          aria-controls={visible ? listId : undefined}
          aria-activedescendant={
            visible && active >= 0 && choices[active]
              ? optionId(active)
              : undefined
          }
          aria-describedby="live-seed-help"
          autoComplete="off"
          autoCapitalize="none"
          spellCheck={false}
          placeholder={`Search a real ${type === "artist" ? "artist" : "film"}`}
          disabled={disabled}
          value={query}
          onChange={(event) => {
            setActive(-1);
            setOpen(true);
            onQuery(event.target.value);
          }}
          onFocus={() => {
            if (!selected) setOpen(true);
          }}
          onKeyDown={(event) => {
            if (event.key === "Escape") {
              event.preventDefault();
              setOpen(false);
              setActive(-1);
            } else if (
              (event.key === "ArrowDown" || event.key === "ArrowUp") &&
              choices.length &&
              !unavailable
            ) {
              event.preventDefault();
              setOpen(true);
              setActive((prior) =>
                event.key === "ArrowDown"
                  ? (visible ? prior + 1 : 0) % choices.length
                  : (visible && prior >= 0
                      ? prior - 1 + choices.length
                      : choices.length - 1) % choices.length,
              );
            } else if (
              event.key === "Enter" &&
              visible &&
              active >= 0 &&
              choices[active]
            ) {
              event.preventDefault();
              select(choices[active]);
            } else if (event.key === "Tab") {
              setOpen(false);
              setActive(-1);
            }
          }}
        />
        <button
          type="button"
          className="seed-toggle"
          aria-label="Show search results"
          aria-expanded={visible}
          aria-controls={visible ? listId : undefined}
          disabled={disabled || unavailable || !choices.length}
          onMouseDown={(event) => event.preventDefault()}
          onClick={() => {
            setOpen(!visible);
            setActive(-1);
            input.current?.focus();
          }}
        >
          <svg
            className="seed-toggle-icon"
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            aria-hidden="true"
          >
            <path
              d="m6 9 6 6 6-6"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
      </div>
      {visible && (
        <div className="seed-popover live-seed-popover">
          <ul
            id={listId}
            className="seed-options"
            role="listbox"
            aria-labelledby={`${id}-label`}
          >
            {choices.map((item, index) => (
              <li
                id={optionId(index)}
                key={item.id}
                role="option"
                aria-selected={selected?.id === item.id}
                className="seed-option"
                data-focused={active === index ? "true" : undefined}
                onMouseDown={(event) => event.preventDefault()}
                onMouseMove={() => setActive(index)}
                onClick={() => select(item)}
              >
                <span className="seed-option-name">{item.name}</span>
                <span className="seed-option-type">
                  {item.type === "artist" ? "Music artist" : "Film"}
                  {item.disambiguation
                    ? ` · ${item.disambiguation}`
                    : " · Qloo entity"}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

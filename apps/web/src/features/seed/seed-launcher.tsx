"use client";

import { useState } from "react";
import Link from "next/link";
import {
  Button,
  ComboBox,
  Input,
  Label,
  ListBox,
  ListBoxItem,
  Popover,
  Text,
} from "react-aria-components";
import { fictionalSeeds, type FictionalSeed } from "./fictional-seeds";

export function SeedLauncher() {
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<FictionalSeed | null>(null);
  const matches = fictionalSeeds.filter((item) =>
    `${item.name} ${item.type}`.toLowerCase().includes(query.toLowerCase()),
  );

  function selectSeed(seed: FictionalSeed) {
    setSelected(seed);
    setQuery(seed.name);
  }

  return (
    <div className="seed-launcher">
      <ComboBox<FictionalSeed>
        className="seed-combobox"
        inputValue={query}
        selectedKey={selected?.id ?? null}
        items={matches}
        menuTrigger="focus"
        allowsEmptyCollection
        onInputChange={(value) => {
          setQuery(value);
          if (value !== selected?.name) setSelected(null);
        }}
        onSelectionChange={(key) => {
          const seed = fictionalSeeds.find((item) => item.id === key);
          if (seed) selectSeed(seed);
        }}
      >
        <Label className="seed-label">Choose your favourite</Label>
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
          <Input
            className="seed-input"
            placeholder="Search a demo artist or film"
            aria-describedby="seed-help"
          />
          <Button
            className="seed-toggle"
            aria-label="Show fictional seed options"
          >
            <span aria-hidden="true">⌄</span>
          </Button>
        </div>
        <Popover className="seed-popover" placement="bottom start">
          <ListBox<FictionalSeed>
            className="seed-options"
            renderEmptyState={() => (
              <div className="seed-empty">
                No fictional match. Try “Velvet” or “Midnight”.
              </div>
            )}
          >
            {(item) => (
              <ListBoxItem
                id={item.id}
                textValue={item.name}
                className="seed-option"
              >
                <Text slot="label" className="seed-option-name">
                  {item.name}
                </Text>
                <Text slot="description" className="seed-option-type">
                  {item.detail}
                </Text>
              </ListBoxItem>
            )}
          </ListBox>
        </Popover>
      </ComboBox>
      <p id="seed-help" className="seed-help">
        Fictional search for this design study. No live data.
      </p>
      <div className="example-seeds" aria-label="Try a fictional favourite">
        <span>TRY</span>
        {fictionalSeeds.slice(0, 3).map((seed) => (
          <button
            className="example-seed"
            type="button"
            key={seed.id}
            onClick={() => selectSeed(seed)}
          >
            {seed.name} <span aria-hidden="true">↗</span>
          </button>
        ))}
      </div>
      <div className="launch-actions">
        {selected ? (
          <Link
            href={`/g/demo?seed=${selected.id}`}
            className="button button-primary"
            data-testid="start-duel"
          >
            Enter the arena <span aria-hidden="true">↗</span>
          </Link>
        ) : (
          <button
            type="button"
            className="button button-primary"
            data-testid="start-duel"
            disabled
          >
            Enter the arena <span aria-hidden="true">↗</span>
          </button>
        )}
        <span className="launch-note">
          One sample round. <br />
          No account. Just curiosity.
        </span>
      </div>
      {selected && (
        <p className="selection-note" role="status">
          Selected {selected.name} · {selected.type} · fictional seed
        </p>
      )}
    </div>
  );
}

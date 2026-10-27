"use client";

import { useContext, useState } from "react";
import { useRouter } from "next/navigation";
import { useFixture } from "../fixtures/provider";
import { Button as ActionButton } from "@/components/ui/button";
import {
  Button,
  ComboBox,
  ComboBoxStateContext,
  Input,
  Label,
  ListBox,
  ListBoxItem,
  Popover,
  Text,
} from "react-aria-components";
import { fictionalSeeds, type FictionalSeed } from "./fictional-seeds";

export function SeedLauncher() {
  const router = useRouter();
  const { actions } = useFixture();
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
        menuTrigger="input"
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
          <SeedSearchInput />
          <Button
            className="seed-toggle"
            aria-label="Show fictional seed options"
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
      {selected && (
        <section
          className="fixture-confirmation"
          aria-labelledby="confirm-seed-title"
        >
          <h2 id="confirm-seed-title">Confirm your seed</h2>
          <p>
            <strong>{selected.name}</strong> · {selected.type}
          </p>
        </section>
      )}
      <div className="launch-actions">
        <ActionButton
          data-testid="start-duel"
          disabled={!selected}
          onClick={() => {
            if (!selected) return;
            actions.start(selected);
            router.push("/g/demo");
          }}
        >
          Start fixture duel <span aria-hidden="true">↗</span>
        </ActionButton>
        <span className="launch-note">
          Five fictional rounds. <br />
          Memory resets on refresh.
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

function SeedSearchInput() {
  const combo = useContext(ComboBoxStateContext);
  return (
    <Input
      className="seed-input"
      placeholder="Search a demo artist or film"
      aria-describedby="seed-help"
      onKeyDownCapture={(event) => {
        if (event.key === "Escape" && combo?.isOpen) {
          // close() commits/reverts a controlled query in this pinned Aria version,
          // which can reopen it. Toggle the open menu without committing a seed.
          // Arrow navigation and selection remain owned by React Aria.
          event.preventDefault();
          event.stopPropagation();
          combo.toggle(null, "manual");
        }
      }}
    />
  );
}

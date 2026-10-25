import type { FixtureRound } from "./types.ts";

/** Invented fixture content, intentionally excluded from production builds. */
export function createFixtureRounds(longTitle = false): FixtureRound[] {
  const pairs = [
    ["Afterlight Assembly", "The Blue Hour Archive"],
    ["The Slow Burn Society", "Neon Daydreams Club"],
    ["Lunar Paper Parade", "Sunday Static Hotel"],
    ["The Quiet Orbit", "Electric Velvet Cinema"],
    ["Atlas of Small Storms", "Glass Midnight Radio"],
  ];
  return pairs.map((titles, index) => ({
    id: `fixture-round-${index + 1}`,
    ordinal: index + 1,
    choices: titles.map((title, side) => ({
      id: `fixture-entity-${index * 2 + side + 1}`,
      title:
        longTitle && index === 0 && side === 0
          ? `${title} and the Unexpectedly Long Journey to the Edge of a Fictional Tomorrow`
          : title,
      kind: "Fictional film",
      art: [
        "/art/afterlight.svg",
        "/art/blue-hour.svg",
        "/art/slow-burn.svg",
        "/art/velvet-static.svg",
      ][(index * 2 + side) % 4],
    })) as FixtureRound["choices"],
  }));
}

/** First card wins rounds 1, 3 and 5; second wins 2 and 4. No Qloo data. */
export function fixtureWinner(round: FixtureRound) {
  return round.choices[(round.ordinal - 1) % 2 === 0 ? 0 : 1];
}

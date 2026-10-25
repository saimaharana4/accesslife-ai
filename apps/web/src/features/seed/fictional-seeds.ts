/** Invented design content. These are not Qloo entities, IDs, results or trends. */
export const fictionalSeeds = [
  {
    id: "demo-velvet-static",
    name: "Velvet Static",
    type: "Music artist",
    detail: "Fictional artist · nocturnal electronics",
  },
  {
    id: "demo-midnight-atlas",
    name: "Midnight Atlas",
    type: "Movie",
    detail: "Fictional film · a journey beyond the city",
  },
  {
    id: "demo-paper-astronauts",
    name: "Paper Astronauts",
    type: "Music artist",
    detail: "Fictional artist · restless dream-pop",
  },
  {
    id: "demo-glass-orchard",
    name: "Glass Orchard",
    type: "Movie",
    detail: "Fictional film · a world slightly out of tune",
  },
] as const;

export type FictionalSeed = (typeof fictionalSeeds)[number];

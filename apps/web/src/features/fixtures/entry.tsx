"use client";

import { LandingStage } from "../seed/landing-stage";
import { FixtureStoryLinks, FixtureGame } from "./game";
import type { FixtureStory } from "./types.ts";

export { FixtureProvider } from "./provider";
export { FixtureGame } from "./game";
export { FixtureResults } from "../results/fixture-results";
export { FixtureChallenge } from "../challenges/fixture-challenge";
export type { FixtureStory } from "./types.ts";

export function FixtureLanding() {
  return (
    <>
      <LandingStage />
      <FixtureStoryLinks />
    </>
  );
}

export function FixtureStories({ story = "normal" }: { story?: FixtureStory }) {
  return <FixtureGame story={story} />;
}

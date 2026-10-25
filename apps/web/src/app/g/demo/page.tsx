import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { FixtureGame, type FixtureStory } from "tasteduel-fixture-entry";
import { fixturesEnabled } from "@/features/mode/config";
export const metadata: Metadata = { title: "The arena" };
export default async function GamePage({
  searchParams,
}: {
  searchParams: Promise<{ story?: string | string[] }>;
}) {
  if (!fixturesEnabled) notFound();
  const { story } = await searchParams;
  const allowed = [
    "normal",
    "empty",
    "partial",
    "retry",
    "expired",
    "interrupted",
    "long-title",
    "missing-image",
  ] as const;
  if (
    story !== undefined &&
    (typeof story !== "string" || !allowed.some((value) => value === story))
  )
    notFound();
  return <FixtureGame story={story as FixtureStory | undefined} />;
}

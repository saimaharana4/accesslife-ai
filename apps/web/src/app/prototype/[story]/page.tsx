import { notFound } from "next/navigation";
import { FixtureStories, type FixtureStory } from "tasteduel-fixture-entry";
import { fixturesEnabled } from "@/features/mode/config";
const stories = [
  "normal",
  "empty",
  "partial",
  "retry",
  "expired",
  "interrupted",
  "long-title",
  "missing-image",
  "preparing",
  "submitting",
  "selected",
  "disabled",
  "pending",
] as const;
export default async function StoryPage({
  params,
}: {
  params: Promise<{ story: string }>;
}) {
  if (!fixturesEnabled) notFound();
  const { story } = await params;
  const normalized =
    story === "loading" ? "preparing" : story === "error" ? "retry" : story;
  if (!stories.some((value) => value === normalized)) notFound();
  return <FixtureStories story={normalized as FixtureStory} />;
}

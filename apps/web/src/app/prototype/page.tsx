import { notFound } from "next/navigation";
import { FixtureStories } from "tasteduel-fixture-entry";
import { fixturesEnabled } from "@/features/mode/config";
export default function StoriesPage() {
  if (!fixturesEnabled) notFound();
  return <FixtureStories story="normal" />;
}

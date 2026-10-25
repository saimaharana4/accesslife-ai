import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { FixtureResults } from "tasteduel-fixture-entry";
import { fixturesEnabled } from "@/features/mode/config";
export const metadata: Metadata = { title: "Your result" };
export default function Page() {
  if (!fixturesEnabled) notFound();
  return <FixtureResults />;
}

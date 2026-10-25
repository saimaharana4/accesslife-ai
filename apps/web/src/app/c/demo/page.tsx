import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { FixtureChallenge } from "tasteduel-fixture-entry";
import { fixturesEnabled } from "@/features/mode/config";
export const metadata: Metadata = { title: "A friendly challenge" };
export default function Page() {
  if (!fixturesEnabled) notFound();
  return <FixtureChallenge />;
}

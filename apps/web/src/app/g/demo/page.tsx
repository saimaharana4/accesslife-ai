import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { DemoArena } from "@/features/duel/demo-arena";
import { fictionalSeeds } from "@/features/seed/fictional-seeds";

export const metadata: Metadata = { title: "The arena" };

export default async function DemoGamePage({
  searchParams,
}: {
  searchParams: Promise<{
    variant?: string | string[];
    seed?: string | string[];
  }>;
}) {
  const params = await searchParams;
  const variant = typeof params.variant === "string" ? params.variant : "";
  const selectedSeed = fictionalSeeds.find((item) => item.id === params.seed);
  if (params.seed !== undefined && !selectedSeed) notFound();
  const seed = selectedSeed ?? fictionalSeeds[0];
  return (
    <DemoArena
      longTitle={variant.includes("long-title")}
      missingImage={variant.includes("missing-image")}
      seedName={seed.name}
      seedType={seed.type}
    />
  );
}

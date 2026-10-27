import { notFound } from "next/navigation";
import { LiveResults } from "@/features/gameplay/live-results";
import { canonicalOrigin } from "@/lib/api/server-challenge";

export const dynamic = "force-dynamic";

export default async function ResultsPage({
  params,
}: {
  params: Promise<{ gameId: string }>;
}) {
  const { gameId } = await params;
  if (
    !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(
      gameId,
    )
  )
    notFound();
  return <LiveResults gameId={gameId} canonicalOrigin={canonicalOrigin()} />;
}

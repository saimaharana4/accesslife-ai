import { notFound } from "next/navigation";
import { LiveResults } from "@/features/gameplay/live-results";

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
  return <LiveResults gameId={gameId} />;
}

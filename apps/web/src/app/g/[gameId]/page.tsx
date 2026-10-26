import { notFound } from "next/navigation";
import { LiveGame } from "@/features/gameplay/live-game";

export default async function GamePage({
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
  return <LiveGame gameId={gameId} />;
}

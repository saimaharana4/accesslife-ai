import type { Metadata } from "next";
import { LiveInvitation } from "@/features/challenges/live-invitation";
import {
  canonicalChallengeUrl,
  readChallengeInvitation,
} from "@/lib/api/server-challenge";

export const dynamic = "force-dynamic";
export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const { invitation } = await readChallengeInvitation(slug);
  const url = canonicalChallengeUrl(slug);
  if (!invitation || !url)
    return {
      title: "Friend challenge",
      robots: { index: false, follow: false },
    };
  const title = `Same five. Your predictions. — ${invitation.seed.name}`;
  const description = `Creator scored ${invitation.creator_score} out of 5. Predict the same five frozen cultural comparisons. Casual play, no timer.`;
  const image = {
    url: `${url}/social`,
    width: 1200,
    height: 630,
    alt: `Taste Duel invitation for ${invitation.seed.name}. Creator prediction score ${invitation.creator_score} out of 5.`,
  };
  return {
    title,
    description,
    alternates: { canonical: url },
    openGraph: { title, description, url, type: "website", images: [image] },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: [image.url],
    },
    robots: { index: false, follow: false },
    referrer: "no-referrer",
  };
}

export default async function ChallengePage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  return <LiveInvitation slug={slug} />;
}

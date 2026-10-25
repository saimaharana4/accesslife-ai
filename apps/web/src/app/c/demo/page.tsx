import type { Metadata } from "next";
import { SampleInvitation } from "@/features/challenges/sample-invitation";
export const metadata: Metadata = { title: "Challenge invitation" };
export default function ChallengePage() {
  return <SampleInvitation />;
}

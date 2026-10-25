import type { Metadata } from "next";
import { SampleResult } from "@/features/results/sample-result";
export const metadata: Metadata = { title: "The result ticket" };
export default function ResultPage() {
  return <SampleResult />;
}

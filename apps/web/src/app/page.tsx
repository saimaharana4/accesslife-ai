import { FixtureLanding } from "tasteduel-fixture-entry";
import { fixturesEnabled } from "@/features/mode/config";
import { LiveLanding } from "@/features/seed/live-landing";
export default function Page() {
  return fixturesEnabled ? <FixtureLanding /> : <LiveLanding />;
}

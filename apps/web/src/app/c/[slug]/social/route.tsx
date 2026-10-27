import { ImageResponse } from "next/og";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { readChallengeInvitation } from "@/lib/api/server-challenge";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
const headers = {
  "Cache-Control": "private, no-store, max-age=0",
  "X-Content-Type-Options": "nosniff",
  "Referrer-Policy": "no-referrer",
};
const font = readFile(
  join(process.cwd(), "public/fonts/BarlowCondensed-Bold.ttf"),
);

/** Original type-and-shape artwork only. No network images or request-selected asset URLs. */
export async function GET(
  _request: Request,
  { params }: { params: Promise<{ slug: string }> },
) {
  const { slug } = await params;
  const { invitation, status } = await readChallengeInvitation(slug);
  if (!invitation)
    return new Response(null, {
      status: status === 410 ? 410 : status === 404 ? 404 : 503,
      headers,
    });
  // next/og otherwise downloads fallback glyphs/emoji. Keep raster rendering
  // within this local font; full original spelling remains in invitation/metadata.
  const name = invitation.seed.name
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^\x20-\x7e]/g, "?")
    .slice(0, 140);
  const artwork = (
    <div
      style={{
        width: "100%",
        height: "100%",
        background: "#101014",
        color: "#F4F1EA",
        display: "flex",
        padding: 54,
        fontFamily: "Barlow",
        position: "relative",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          width: 820,
          justifyContent: "space-between",
        }}
      >
        <div style={{ display: "flex", fontSize: 36, letterSpacing: 4 }}>
          TASTE <span style={{ color: "#DBFF5E", marginLeft: 10 }}>DUEL</span>
        </div>
        <div style={{ display: "flex", flexDirection: "column" }}>
          <div style={{ display: "flex", fontSize: 92, lineHeight: 0.95 }}>
            SAME FIVE.
          </div>
          <div
            style={{
              display: "flex",
              fontSize: 82,
              lineHeight: 1.05,
              color: "#DBFF5E",
            }}
          >
            YOUR PREDICTIONS.
          </div>
        </div>
        <div
          style={{ display: "flex", flexDirection: "column", maxWidth: 770 }}
        >
          <div
            style={{
              fontSize: name.length > 80 ? 28 : 36,
              overflowWrap: "anywhere",
              lineHeight: 1.15,
            }}
          >
            {name}
          </div>
          <div
            style={{
              display: "flex",
              fontSize: 24,
              color: "#B9A9FF",
              marginTop: 12,
            }}
          >
            {invitation.source === "qloo"
              ? "FROZEN QLOO COMPARISONS"
              : "SYNTHETIC FIXTURE CHALLENGE"}{" "}
            · NO TIMER
          </div>
        </div>
      </div>
      <div
        style={{
          position: "absolute",
          right: 44,
          top: 58,
          bottom: 58,
          width: 220,
          borderLeft: "2px dashed #8A8299",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          paddingLeft: 22,
        }}
      >
        <div style={{ display: "flex", fontSize: 25, color: "#B9A9FF" }}>
          CREATOR SCORE
        </div>
        <div
          style={{
            display: "flex",
            fontSize: 158,
            lineHeight: 1.1,
            color: "#DBFF5E",
          }}
        >
          {invitation.creator_score}
          <span
            style={{ fontSize: 58, alignSelf: "flex-end", marginBottom: 20 }}
          >
            /5
          </span>
        </div>
        <div style={{ display: "flex", fontSize: 24 }}>CAN YOU MATCH IT?</div>
        <div
          style={{
            display: "flex",
            marginTop: 34,
            fontSize: 70,
            color: "#B9A9FF",
          }}
        >
          <svg width="68" height="68" viewBox="0 0 68 68">
            <path
              fill="#B9A9FF"
              d="M30 0h8v23L54 7l6 6-16 17h24v8H44l16 17-6 6-16-16v23h-8V45L14 61l-6-6 16-17H0v-8h24L8 13l6-6 16 16Z"
            />
          </svg>
        </div>
      </div>
    </div>
  );
  return new ImageResponse(artwork, {
    width: 1200,
    height: 630,
    headers,
    fonts: [{ name: "Barlow", data: await font, weight: 700, style: "normal" }],
  });
}

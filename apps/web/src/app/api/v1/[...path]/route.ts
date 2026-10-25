// The prototype never forwards to the legacy planner or a live provider.
// Authenticated Taste Duel forwarding is implemented in Prompt 10.
function unavailable() {
  return Response.json(
    {
      error: {
        code: "PROTOTYPE_ONLY",
        message:
          "This visual prototype uses local synthetic content. Live game APIs are not connected.",
      },
    },
    { status: 503, headers: { "Cache-Control": "no-store" } },
  );
}

export {
  unavailable as GET,
  unavailable as POST,
  unavailable as PUT,
  unavailable as PATCH,
  unavailable as DELETE,
};

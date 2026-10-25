// Both conditions are compiled by Next. A runtime key or URL cannot enable a
// fixture route in a production build. The module alias also excludes its code.
export const fixturesEnabled =
  process.env.NODE_ENV === "development" &&
  process.env.NEXT_PUBLIC_TASTEDUEL_FIXTURES === "1";

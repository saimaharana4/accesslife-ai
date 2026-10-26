// Loopback production preview. Uses the separately metered private live API.
process.env.TASTEDUEL_API_URL = "http://127.0.0.1:8004";
process.env.TASTEDUEL_WEB_ORIGINS = "http://127.0.0.1:3001";
process.env.TASTEDUEL_ALLOW_LOCAL_HTTP = "true";
process.env.TASTEDUEL_API_IAM = "false";
await import("./start-prototype.mjs");

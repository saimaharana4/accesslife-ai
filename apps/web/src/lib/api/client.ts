import type { components } from "./schema";
export type City = components["schemas"]["City"];
export type Place = components["schemas"]["Place"];
export type Evidence = components["schemas"]["Evidence"];
export type PlanInput = components["schemas"]["PlanInput"];
export type TripSegment = components["schemas"]["TripSegment"];
export type Plan = components["schemas"]["PlanSnapshot"];
export type Trip = components["schemas"]["TripSnapshot"];
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}
export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init.headers },
    cache: "no-store",
  });
  const data = await response.json();
  if (!response.ok)
    throw new ApiError(
      data.error?.message ||
        "The request could not be completed. Please retry.",
      response.status,
    );
  return data as T;
}

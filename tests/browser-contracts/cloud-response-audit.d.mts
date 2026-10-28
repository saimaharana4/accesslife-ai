/** Test observer only; production DTOs remain generated from Python OpenAPI. */
export interface ResponseAudit {
  readonly findings: string[];
  inspect(text: string): boolean;
  confirmControlled(key: string, text: string): boolean;
  unavailable(key: string | undefined): boolean;
  readonly confirmedControlled: number;
  readonly expectedUnavailable: number;
}

export function createResponseAudit(token: string): ResponseAudit;

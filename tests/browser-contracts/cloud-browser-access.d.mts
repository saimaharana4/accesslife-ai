export type CloudBrowserAccess = {
  mode: "private" | "public";
  origin: string;
  identityToken: string | null;
  privateApiOrigin: string | null;
};
export function cloudBrowserAccess(
  env: Record<string, string | undefined>,
): CloudBrowserAccess;

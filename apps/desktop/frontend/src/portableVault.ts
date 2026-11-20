import type { desktopComponents } from "@wenyi/shared-schema";
import { request } from "./transport";

export type PortableVaultStatus = desktopComponents["schemas"]["PortableVaultStatus"];

export const portableVaultQuery = {
  queryKey: ["portable-vault"],
  queryFn: () => request<PortableVaultStatus>("/desktop/portable-credentials"),
  retry: false,
  refetchOnWindowFocus: false,
  refetchOnReconnect: false,
} as const;

export const createPortableVault = (passphrase: string) =>
  request<PortableVaultStatus>("/desktop/portable-credentials/create", {
    method: "POST",
    body: JSON.stringify({ passphrase }),
  });

export const unlockPortableVault = (passphrase: string) =>
  request<PortableVaultStatus>("/desktop/portable-credentials/unlock", {
    method: "POST",
    body: JSON.stringify({ passphrase }),
  });

export const lockPortableVault = () =>
  request<PortableVaultStatus>("/desktop/portable-credentials/lock", { method: "POST" });

export const changePortablePassphrase = (current: string, next: string) =>
  request<PortableVaultStatus>("/desktop/portable-credentials/passphrase", {
    method: "POST",
    body: JSON.stringify({ current, next }),
  });

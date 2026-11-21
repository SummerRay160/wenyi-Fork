import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { credentialQuery, readCredential } from "./credentials";
import { updateCredentialSafety } from "./updateSafety";
import { useDesktopI18n } from "./i18n";
import { PortableVaultDialog } from "./PortableCredentials";
import { portableVaultQuery } from "./portableVault";
import type { CredentialFieldProps } from "@wenyi/ui/platform";
import { ErrorNotice, Button, PasswordInput } from "@wenyi/ui/primitives";
import { SettingsRow, SETTINGS_CONTROL_CLASSNAME } from "@wenyi/ui/settings";

/**
 * API key field. A saved manual key is loaded into the field masked with dots;
 * the eye button reveals it. Unsaved edits belong to the provider dialog.
 */
export function DesktopCredential({ connection, storedConnection, edit, onEdit }: CredentialFieldProps) {
  const { t } = useDesktopI18n();
  const credentials = useQuery(credentialQuery);
  const status = storedConnection ? credentials.data?.[storedConnection] : undefined;
  const portable = useQuery(portableVaultQuery);
  const [stored, setStored] = useState<{ id: string; value: string }>();
  const [vaultOpen, setVaultOpen] = useState(false);
  const manual = status?.mode === "manual" && status.available;
  // Load the stored key once per connection so the field shows it masked.
  useEffect(() => {
    if (!storedConnection || !manual) return;
    let active = true;
    readCredential(storedConnection)
      .then(value => { if (active) setStored({ id: storedConnection, value }); })
      // An unreadable saved key must not block entering a replacement.
      .catch(() => { if (active) setStored(undefined); });
    return () => { active = false; };
  }, [storedConnection, manual]);
  const hasEdit = edit !== undefined;
  useEffect(() => {
    const field = Symbol("provider-key");
    updateCredentialSafety(field, hasEdit);
    return () => updateCredentialSafety(field, false);
  }, [hasEdit]);
  const savedValue = manual && stored?.id === storedConnection ? stored?.value : undefined;
  const placeholder = edit === undefined && status?.mode === "environment" && status.available
    ? t("credentials.environmentPlaceholder", { name: status.environment || "" })
    : status && !status.requires_key
      ? t("credentials.notRequired")
      : t("credentials.placeholder");
  const inputId = `credential-secret-${connection}`;
  // A locked portable vault keeps saved keys session-bound until it is unlocked,
  // so the row points at Unlock/Set up right where the session hint appears.
  const description =
    (manual && status.storage === "session") ||
    (portable.data?.supported && !portable.data.unlocked && status?.mode === "manual")
      ? (
        <>
          {manual && status.storage === "session" && <>{t("credentials.sessionHelp")}{" "}</>}
          {portable.data?.supported && !portable.data.unlocked && status?.mode === "manual" && (
            <>
              {t("credentials.portableSessionHelp")}{" "}
              <button
                type="button"
                className="underline underline-offset-2"
                onClick={() => setVaultOpen(true)}
              >
                {t(portable.data.present ? "portable.unlock" : "portable.setUp")}
              </button>
            </>
          )}
        </>
      )
      : undefined;
  return (
    <>
      <SettingsRow
        label={t("credentials.key")}
        htmlFor={inputId}
        description={description}
        control={
          <div className="w-full">
            <PasswordInput id={inputId} className={SETTINGS_CONTROL_CLASSNAME}
              value={edit ?? savedValue ?? ""}
              placeholder={placeholder}
              showLabel={t("credentials.show")}
              hideLabel={t("credentials.hide")}
              onChange={({ target: { value } }) => onEdit(value === savedValue ? undefined : value)}
            />
          </div>
        }
        detail={credentials.error && <>
          <ErrorNotice error={credentials.error} />
          <Button type="button" variant="ghost" size="sm" disabled={credentials.isFetching}
            onClick={() => void credentials.refetch()}>{t("credentials.refresh")}</Button>
        </>}
      />
      <PortableVaultDialog
        open={vaultOpen}
        mode={portable.data?.present ? "unlock" : "create"}
        onClose={() => setVaultOpen(false)}
        onChanged={() => {
          void portable.refetch();
          void credentials.refetch();
        }}
      />
    </>
  );
}

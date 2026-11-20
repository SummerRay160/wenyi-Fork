import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, Dialog, Label, PasswordInput } from "@wenyi/ui/primitives";
import { SettingsRow } from "@wenyi/ui/settings";
import { credentialQuery } from "./credentials";
import { useDesktopI18n } from "./i18n";
import { mineruCredentialQuery } from "./mineruCredentials";
import {
  changePortablePassphrase,
  createPortableVault,
  lockPortableVault,
  portableVaultQuery,
  unlockPortableVault,
} from "./portableVault";

type DialogMode = "create" | "unlock" | "change";

/** Shared passphrase dialog for the settings row and the credential fields. */
export function PortableVaultDialog({
  open,
  mode,
  onClose,
  onChanged,
}: {
  open: boolean;
  mode: DialogMode;
  onClose: () => void;
  onChanged?: () => void;
}) {
  const { t } = useDesktopI18n();
  const queryClient = useQueryClient();
  const [passphrase, setPassphrase] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [current, setCurrent] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<"short" | "mismatch" | "failed" | null>(null);
  const needsConfirmation = mode !== "unlock";
  const title = t(
    mode === "create"
      ? "portable.createTitle"
      : mode === "unlock"
        ? "portable.unlockTitle"
        : "portable.changeTitle",
  );
  const help = t(
    mode === "create"
      ? "portable.createHelp"
      : mode === "unlock"
        ? "portable.unlockHelp"
        : "portable.changeHelp",
  );
  const reset = () => {
    setPassphrase("");
    setConfirmation("");
    setCurrent("");
    setError(null);
  };
  const close = () => {
    if (pending) return;
    reset();
    onClose();
  };
  const finish = () => {
    reset();
    onClose();
  };
  const submit = async () => {
    if (pending) return;
    if (needsConfirmation && passphrase.length < 8) {
      setError("short");
      return;
    }
    if (needsConfirmation && passphrase !== confirmation) {
      setError("mismatch");
      return;
    }
    if (!passphrase || (mode === "change" && !current)) {
      setError("failed");
      return;
    }
    setPending(true);
    setError(null);
    try {
      const result =
        mode === "create"
          ? await createPortableVault(passphrase)
          : mode === "unlock"
            ? await unlockPortableVault(passphrase)
            : await changePortablePassphrase(current, passphrase);
      queryClient.setQueryData(portableVaultQuery.queryKey, result);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: credentialQuery.queryKey }),
        queryClient.invalidateQueries({ queryKey: mineruCredentialQuery.queryKey }),
      ]);
      onChanged?.();
      finish();
    } catch {
      setError("failed");
    } finally {
      setPending(false);
    }
  };
  return (
    <Dialog
      open={open}
      onClose={close}
      closeDisabled={pending}
      title={title}
      description={help}
    >
      <div className="space-y-3">
        {mode === "change" && (
          <>
            <Label htmlFor="portable-current">{t("portable.currentPassphrase")}</Label>
            <PasswordInput
              id="portable-current"
              value={current}
              showLabel={t("credentials.show")}
              hideLabel={t("credentials.hide")}
              onChange={(event) => setCurrent(event.target.value)}
            />
          </>
        )}
        <Label htmlFor="portable-passphrase">
          {t(mode === "change" ? "portable.newPassphrase" : "portable.passphrase")}
        </Label>
        <PasswordInput
          id="portable-passphrase"
          value={passphrase}
          showLabel={t("credentials.show")}
          hideLabel={t("credentials.hide")}
          onChange={(event) => setPassphrase(event.target.value)}
        />
        {needsConfirmation && (
          <>
            <Label htmlFor="portable-confirmation">{t("portable.confirmPassphrase")}</Label>
            <PasswordInput
              id="portable-confirmation"
              value={confirmation}
              showLabel={t("credentials.show")}
              hideLabel={t("credentials.hide")}
              onChange={(event) => setConfirmation(event.target.value)}
            />
          </>
        )}
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {t(
              error === "short"
                ? "portable.passphraseTooShort"
                : error === "mismatch"
                  ? "portable.passphraseMismatch"
                  : "portable.failed",
            )}
          </p>
        )}
        <div className="flex flex-wrap gap-2">
          <Button disabled={pending} onClick={() => void submit()}>
            {t(
              mode === "create"
                ? "portable.submitCreate"
                : mode === "unlock"
                  ? "portable.submitUnlock"
                  : "portable.submitChange",
            )}
          </Button>
          <Button variant="outline" disabled={pending} onClick={close}>
            {t("portable.cancel")}
          </Button>
        </div>
      </div>
    </Dialog>
  );
}

export function PortableCredentials() {
  const { t } = useDesktopI18n();
  const query = useQuery(portableVaultQuery);
  const queryClient = useQueryClient();
  const [dialog, setDialog] = useState<DialogMode | null>(null);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  const data = query.data;
  if (!data?.supported) return null;
  const lock = async () => {
    setBusy(true);
    setFailed(false);
    try {
      const result = await lockPortableVault();
      queryClient.setQueryData(portableVaultQuery.queryKey, result);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: credentialQuery.queryKey }),
        queryClient.invalidateQueries({ queryKey: mineruCredentialQuery.queryKey }),
      ]);
    } catch {
      setFailed(true);
    } finally {
      setBusy(false);
    }
  };
  const description = !data.present
    ? t("portable.setupHelp")
    : !data.unlocked
      ? t("portable.lockedHelp")
      : `${t("portable.unlockedHelp")} ${t(
          data.auto_unlock ? "portable.autoUnlock" : "portable.noAutoUnlock",
        )}`;
  return (
    <>
      <SettingsRow
        label={t("portable.title")}
        description={description}
        control={
          !data.present ? (
            <Button size="sm" onClick={() => setDialog("create")}>
              {t("portable.setUp")}
            </Button>
          ) : !data.unlocked ? (
            <Button size="sm" onClick={() => setDialog("unlock")}>
              {t("portable.unlock")}
            </Button>
          ) : (
            <div className="flex flex-wrap justify-end gap-2">
              <Button variant="outline" size="sm" disabled={busy} onClick={() => void lock()}>
                {t("portable.lock")}
              </Button>
              <Button variant="ghost" size="sm" onClick={() => setDialog("change")}>
                {t("portable.changePassphrase")}
              </Button>
            </div>
          )
        }
        detail={
          (query.isError || failed) && (
            <p role="alert" className="text-sm text-destructive">
              {t("portable.failed")}
            </p>
          )
        }
      />
      <PortableVaultDialog
        open={dialog !== null}
        mode={dialog ?? "create"}
        onClose={() => setDialog(null)}
        onChanged={() => {
          void query.refetch();
        }}
      />
    </>
  );
}

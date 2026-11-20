# Windows portable edition

This fork publishes a **Windows x64 portable edition** as the portable variant of the
upstream stable release. It is built from the same stable Git tag as that release, so its
version matches the tag without a development or local suffix. Upstream synchronization
must preserve it. The installed edition, its NSIS installer, its default data root and its
update path are unchanged.

The portable edition is built only by
[`.github/workflows/desktop-portable.yml`](../../.github/workflows/desktop-portable.yml).
There is no local portable build command.

## Package and data layout

The release asset is `wenyi-desktop-<version>-windows-x64-portable.zip`. Extract it
anywhere writable on a local disk:

```text
Wenyi-Desktop-<version>-windows-x64-portable/
  wenyi-desktop.exe
  portable.marker
  sidecar/wenyi-engine/wenyi-engine.exe
  README.txt
  LICENSE
```

The first launch creates `data/` beside the executable. It contains the catalog,
projects, logs, locks, WebView data, plugin runtime and manual backups. The portable
edition does not read or write `%LOCALAPPDATA%\Wenyi\Desktop`.

`data/` is intentionally inside the program folder. `apps/desktop/src/paths.rs` admits
exactly one overlap in portable mode: the normalized data root must equal
`<install>/data`. Every other install/data overlap remains refused, including
`<install>` itself, other children and `--data-dir` targets that overlap the install.
An explicit `--data-dir` always wins over the portable default.

## Mode detection

`apps/desktop/src/portable.rs` owns the marker name, the data directory name and the
portable application identity. Portable mode is active when the executable's directory
contains a regular `portable.marker` file. The Rust parent passes `--portable` to the
engine; the engine never infers the mode from its own sidecar path.

The portable build uses the Toast/taskbar identity `org.wenyi.desktop.portable`, while
the installed build keeps `org.wenyi.desktop`. The two editions can run together without
overwriting each other's HKCU registration.

## Updates

Portable builds use the existing manual update mode. **Settings → About** can check the
fork's GitHub Releases and show the new version and notes, but it never launches the
NSIS installer. `desktop_update_install` also refuses portable builds defensively.

Update by downloading the new portable ZIP, quitting Wenyi, replacing the program files
and keeping `data/`. The ZIP is not part of the signed updater manifest.

## Portable credentials

Saved model and MinerU keys are encrypted in `data/credentials.vault`; they travel with
the folder and are never written in plaintext to JSON, SQLite or logs.

- A random 32-byte data key encrypts the vault payload with AES-256-GCM.
- The data key is wrapped with a scrypt-derived key from the user's passphrase
  (`N=2^15`, `r=8`, `p=1`, 16-byte salt).
- `data/credentials.dpapi` may cache the data key with Windows DPAPI for the current
  user. It is a convenience only: a copied folder on another machine or Windows user
  stays locked and asks for the passphrase.
- **Lock** clears memory and deletes the DPAPI wrapper, so the next launch requires the
  passphrase. **Unlock** re-arms the wrapper.
- A successful passphrase unlock on a new machine or user writes a fresh wrapper.
- Losing the passphrase makes the saved keys unrecoverable. Deleting the vault resets
  the store but does not recover the keys.

The UI is **Settings → General → Portable credentials**. Model and MinerU credential
fields show a hint when the vault is absent or locked. Saving without a vault remains
session-only and visible, never silently persisted.

Multiple Windows users sharing one portable folder are not promised automatic unlock.
The DPAPI wrapper belongs to the user who wrote it; other users must enter the
passphrase, and the last successful wrapper write replaces the previous one.

## Build and release

A portable build always starts from a stable release tag: `vX.Y.Z`. The workflow triggers
on a published GitHub Release and on manual dispatch with a required `tag` input; both
paths use that tag as the single source of truth. There is no development-checkout build.
It builds only on `windows-latest`:

1. Validate the tag against the stable-version pattern and resolve `version` as the tag
   without its leading `v`.
2. Check out that tag, resolve the Git version, and set `WENYI_UPDATE_REPO` to the
   workflow's own repository.
3. Assert the resolved version equals the tag version, then build the native lock library,
   install the frontend dependencies and run `pnpm desktop:build --no-bundle`.
4. Verify the GUI PE subsystem, then run `scripts/release/package_portable.py`.
5. Extract the ZIP, run `wenyi-desktop.exe --version`, and require the marker and sidecar
   engine. The archive must not contain `data/`.
6. Upload a workflow artifact for manual runs, or append the ZIP and
   `wenyi-desktop-portable-SHA256SUMS.txt` to the Release when publishing.

Manual `workflow_dispatch` requires a stable tag. With `publish=false` it produces an
artifact only; `publish=true` additionally requires an already published stable release.
The portable version is exactly the tag without `v` — never a `-dev.N` or `+local` build
suffix. The workflow never calls `desktop_updates.py` and never creates an updater manifest.

The package script is `scripts/release/package_portable.py`; the packaged bilingual
README source is `scripts/release/portable-readme.md`. The repository ignores `*.txt`, so
the source keeps the `.md` name while the archive entry remains `README.txt`.

## Verification

Validate a downloaded artifact, not a local portable build:

- extract to a short writable path and run `wenyi-desktop.exe --version`;
- confirm `portable.marker` and `sidecar/wenyi-engine/wenyi-engine.exe` exist;
- launch without system Python or services, create a project and verify `data/` is used;
- set a passphrase, save a key, restart and confirm automatic unlock, then copy the folder
  and confirm the passphrase is required on the copy;
- check that **Check for updates** shows releases but no install button;
- test the missing-WebView2 message and the unsigned SmartScreen warning.

The static workflow contract lives in `packages/core/tests/test_release_packaging.py`.
GitHub Actions syntax and the actual Windows build can only be validated by dispatching
the workflow with a stable tag.

## Upstream synchronization checklist

When merging upstream changes, preserve all of the following:

- `portable.marker` detection, `<exe>/data`, and the single-path layout exception;
- the `--portable` engine flag and `org.wenyi.desktop.portable` identity;
- manual-only updates and the portable install refusal;
- `PortableVault`, its DPAPI wrapper, and `CredentialStore`'s `portable` storage label;
- the portable credential router and the generated schema entries;
- the Settings panel, credential hints and bilingual copy;
- `scripts/release/package_portable.py`, its README source and tests;
- `.github/workflows/desktop-portable.yml` and its contract test;
- this page, its Chinese counterpart, and the AGENTS.md entry points.

High-conflict files: `apps/desktop/src/{paths,main,process,updates}.rs`,
`apps/desktop/src/notifications/{mod,windows}.rs`,
`apps/desktop/backend/wenyi_desktop/{local_credentials,main,desktop}.py`,
`apps/desktop/frontend/src/{platform,DesktopCredential,MinerUCredential,i18n}.tsx`,
and the generated `packages/shared-schema/src/desktop.d.ts`. Re-run the portable unit
tests, the packaging tests and `pnpm check:schema` after upstream merges.

## Limitations

- Windows x64 only; no Linux or macOS portable package.
- The engine is a PyInstaller onedir sidecar, so the package is a folder, not a single
  executable.
- Microsoft Edge WebView2 Runtime is required; the portable package does not install it.
- The executable is not OS-signed; SmartScreen warnings are expected.
- Toast registration writes one per-user HKCU identity. No credentials or book text are
  written there.
- The installed edition's data root is not migrated automatically. Use **Import existing
  project** for old projects and re-enter settings and keys.

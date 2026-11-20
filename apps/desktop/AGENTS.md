# Wenyi Desktop agent guide

Read the repository [AGENTS.md](../../AGENTS.md) first. This directory also carries the
fork-only Windows x64 portable edition.

Before changing paths, updates, credentials, notifications, packaging, or the release
workflow, read [Portable edition](../../docs/development/portable-edition.md). Preserve:

- `portable.marker` detection, the `<exe>/data` default root, and the single layout
  exception in `src/paths.rs`;
- the `--portable` engine flag and the separate `org.wenyi.desktop.portable` identity;
- manual-only updates and the portable install refusal;
- `PortableVault`, its DPAPI wrapper, the `portable` storage label, and the local API;
- the Settings panel, credential hints and bilingual copy;
- `scripts/release/package_portable.py`, `.github/workflows/desktop-portable.yml`, and
  their tests.

Build the portable edition only through `.github/workflows/desktop-portable.yml`; do not
add a local portable build path. The installed edition's installer, data root and update
path must remain unchanged.

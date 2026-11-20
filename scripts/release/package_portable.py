"""Create the fork-only Windows x64 portable ZIP from the built app and sidecar."""

from __future__ import annotations

import argparse
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MARKER_TEXT = "Wenyi Desktop portable edition. Keep this file beside wenyi-desktop.exe.\n"
VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?")


def _file(source: Path, name: str, archive: zipfile.ZipFile) -> None:
    if source.is_symlink() or not source.is_file():
        raise ValueError(f"Missing portable package file: {source}")
    archive.write(source, name)


def package(
    binary: Path,
    sidecar: Path,
    output: Path,
    version: str,
    *,
    readme: Path,
    license_path: Path,
) -> Path:
    """Require the built Windows executable and engine; never overwrite a ZIP."""
    if not VERSION.fullmatch(version):
        raise ValueError("Expected a native semantic version")
    if binary.name != "wenyi-desktop.exe" or binary.is_symlink() or not binary.is_file():
        raise ValueError("Expected the built wenyi-desktop.exe")
    if not sidecar.is_dir():
        raise ValueError("Missing sidecar wenyi-engine directory")
    engine = sidecar / "wenyi-engine.exe"
    if engine.is_symlink() or not engine.is_file():
        raise ValueError("Missing sidecar wenyi-engine/wenyi-engine.exe")
    if not readme.is_file():
        raise ValueError("Missing portable README")
    if not license_path.is_file():
        raise ValueError("Missing LICENSE")
    output.mkdir(parents=True, exist_ok=True)
    target = output / f"wenyi-desktop-{version}-windows-x64-portable.zip"
    if target.exists():
        raise ValueError(f"Refusing to overwrite {target}")
    root = f"Wenyi-Desktop-{version}-windows-x64-portable"
    engine_root = f"{root}/sidecar/wenyi-engine"
    try:
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            _file(binary, f"{root}/{binary.name}", archive)
            _file(readme, f"{root}/README.txt", archive)
            _file(license_path, f"{root}/LICENSE", archive)
            archive.writestr(f"{root}/portable.marker", MARKER_TEXT)
            _file(engine, f"{engine_root}/wenyi-engine.exe", archive)
            for source in sorted(sidecar.rglob("*")):
                if source == engine or source.is_dir():
                    continue
                _file(source, f"{engine_root}/{source.relative_to(sidecar).as_posix()}", archive)
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--sidecar", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=Path("release-assets"))
    parser.add_argument(
        "--readme",
        type=Path,
        default=ROOT / "scripts/release/portable-readme.md",
    )
    parser.add_argument("--license", type=Path, default=ROOT / "LICENSE")
    args = parser.parse_args()
    target = package(
        args.binary,
        args.sidecar,
        args.output,
        args.version,
        readme=args.readme,
        license_path=args.license,
    )
    print(target)


if __name__ == "__main__":
    main()

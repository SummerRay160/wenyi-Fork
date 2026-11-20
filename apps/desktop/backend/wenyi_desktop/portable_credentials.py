"""Passphrase-encrypted Desktop credentials that travel with the data folder.

The vault keeps one random data key wrapped by a scrypt-derived key. Secrets are
encrypted with the data key, so changing the passphrase only rewraps that key.
Windows DPAPI may cache the data key for the current user; a copied folder on
another machine or user stays locked until the passphrase is entered.
"""

from __future__ import annotations

import base64
import ctypes
import hashlib
import json
import os
import sys
import tempfile
import threading
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

VAULT_FILE = "credentials.vault"
DPAPI_FILE = "credentials.dpapi"
VAULT_VERSION = 1
KEY_BYTES = 32
SALT_BYTES = 16
NONCE_BYTES = 12
KDF_N = 2**15
KDF_R = 8
KDF_P = 1
KDF_MAXMEM = 64 * 1024 * 1024
MIN_PASSPHRASE = 8
MAX_PASSPHRASE = 1024


class PortableVaultError(RuntimeError):
    """A portable vault operation failed without exposing secret material."""


class PortableVaultLocked(PortableVaultError):
    """The vault is present but no key is available in this process."""


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", ctypes.c_uint32),
        ("pbData", ctypes.POINTER(ctypes.c_char)),
    ]


class DpapiProtector:
    """Wrap the data key with the current Windows user's DPAPI key."""

    _FLAGS = 0x1  # CRYPTPROTECT_UI_FORBIDDEN

    def available(self) -> bool:
        return sys.platform == "win32"

    def protect(self, value: bytes) -> bytes:
        return self._call("CryptProtectData", value)

    def unprotect(self, value: bytes) -> bytes:
        return self._call("CryptUnprotectData", value)

    def _call(self, name: str, value: bytes) -> bytes:
        if not self.available():
            raise PortableVaultError("Windows DPAPI is unavailable")
        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        buffer = ctypes.create_string_buffer(value, len(value))
        source = _DataBlob(len(value), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))
        result = _DataBlob()
        if name == "CryptProtectData":
            ok = crypt32.CryptProtectData(
                ctypes.byref(source),
                None,
                None,
                None,
                None,
                self._FLAGS,
                ctypes.byref(result),
            )
        else:
            ok = crypt32.CryptUnprotectData(
                ctypes.byref(source),
                None,
                None,
                None,
                None,
                self._FLAGS,
                ctypes.byref(result),
            )
        if not ok:
            raise PortableVaultError("Windows DPAPI could not process the portable key")
        try:
            return ctypes.string_at(result.pbData, result.cbData)
        finally:
            kernel32.LocalFree(result.pbData)


def _b64(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.b64decode(value, validate=True)


def _validate_passphrase(passphrase: str) -> None:
    if not MIN_PASSPHRASE <= len(passphrase) <= MAX_PASSPHRASE or "\x00" in passphrase:
        raise PortableVaultError("Passphrase must be 8 to 1024 characters")


def _derive(passphrase: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(
        passphrase.encode("utf-8"),
        salt=salt,
        n=n,
        r=r,
        p=p,
        dklen=KEY_BYTES,
        maxmem=KDF_MAXMEM,
    )


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if os.name != "nt":
            os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


class PortableVault:
    """File-backed credentials shared by the engine and the local API."""

    storage = "portable"

    def __init__(self, workspace: Path, *, protector=None) -> None:
        self.workspace = Path(workspace)
        self._protector = protector or DpapiProtector()
        self._mutex = threading.RLock()
        self._key: bytes | None = None
        self._secrets: dict[str, str] = {}
        self._salt = b""
        self._kdf = (KDF_N, KDF_R, KDF_P)
        self._key_nonce = b""
        self._wrapped_key = b""
        self._auto_unlock = False
        if self.present:
            self.try_auto_unlock()

    @property
    def vault_path(self) -> Path:
        return self.workspace / VAULT_FILE

    @property
    def dpapi_path(self) -> Path:
        return self.workspace / DPAPI_FILE

    @property
    def present(self) -> bool:
        return self.vault_path.is_file()

    @property
    def unlocked(self) -> bool:
        return self._key is not None

    @property
    def auto_unlock(self) -> bool:
        return self._auto_unlock

    def status(self) -> dict:
        with self._mutex:
            return {
                "present": self.present,
                "unlocked": self.unlocked,
                "auto_unlock": self.auto_unlock,
            }

    def create(self, passphrase: str) -> None:
        with self._mutex:
            _validate_passphrase(passphrase)
            if self.present:
                raise PortableVaultError("Portable credential vault already exists")
            self.dpapi_path.unlink(missing_ok=True)
            key = os.urandom(KEY_BYTES)
            salt = os.urandom(SALT_BYTES)
            self._derive_and_wrap(passphrase, salt, key)
            self._key = key
            self._secrets = {}
            self._save_payload()
            self._arm_auto_unlock()

    def unlock(self, passphrase: str, *, remember: bool = True) -> None:
        with self._mutex:
            _validate_passphrase(passphrase)
            container = self._read_container()
            salt = _unb64(container["kdf"]["salt"])
            n = int(container["kdf"]["n"])
            r = int(container["kdf"]["r"])
            p = int(container["kdf"]["p"])
            try:
                wrapped = AESGCM(_derive(passphrase, salt, n, r, p)).decrypt(
                    _unb64(container["key_nonce"]), _unb64(container["wrapped_key"]), None
                )
                secrets = self._decrypt_payload(container, wrapped)
            except PortableVaultError:
                raise
            except Exception:
                raise PortableVaultError("Incorrect passphrase") from None
            self._key = wrapped
            self._secrets = secrets
            self._salt = salt
            self._kdf = (n, r, p)
            self._key_nonce = _unb64(container["key_nonce"])
            self._wrapped_key = _unb64(container["wrapped_key"])
            self._auto_unlock = False
            if remember:
                self._arm_auto_unlock()

    def lock(self) -> None:
        with self._mutex:
            self._key = None
            self._secrets = {}
            self._salt = b""
            self._key_nonce = b""
            self._wrapped_key = b""
            self._auto_unlock = False
            self.dpapi_path.unlink(missing_ok=True)

    def change_passphrase(self, current: str, new: str) -> None:
        with self._mutex:
            _validate_passphrase(current)
            _validate_passphrase(new)
            self.unlock(current, remember=False)
            if self._key is None:
                raise PortableVaultLocked("Portable credential vault is locked")
            salt = os.urandom(SALT_BYTES)
            self._derive_and_wrap(new, salt, self._key)
            self._save_payload()
            self._arm_auto_unlock()

    def try_auto_unlock(self) -> bool:
        with self._mutex:
            if not self.present or not self.dpapi_path.is_file():
                return False
            try:
                if not self._protector.available():
                    return False
                key = self._protector.unprotect(self.dpapi_path.read_bytes())
                container = self._read_container()
                secrets = self._decrypt_payload(container, key)
                self._key = key
                self._secrets = secrets
                self._set_key_material(container)
                self._auto_unlock = True
                return True
            except Exception:
                return False

    def get_password(self, service: str, reference: str) -> str | None:
        with self._mutex:
            self._require_unlocked()
            return self._secrets.get(self._secret_key(service, reference))

    def set_password(self, service: str, reference: str, secret: str) -> None:
        with self._mutex:
            self._require_unlocked()
            self._secrets[self._secret_key(service, reference)] = secret
            self._save_payload()

    def delete_password(self, service: str, reference: str) -> None:
        with self._mutex:
            self._require_unlocked()
            if self._secrets.pop(self._secret_key(service, reference), None) is not None:
                self._save_payload()

    def _require_unlocked(self) -> None:
        if self._key is None:
            raise PortableVaultLocked("Portable credential vault is locked")

    @staticmethod
    def _secret_key(service: str, reference: str) -> str:
        return f"{service}:{reference}"

    def _derive_and_wrap(self, passphrase: str, salt: bytes, key: bytes) -> None:
        self._salt = salt
        self._kdf = (KDF_N, KDF_R, KDF_P)
        self._key_nonce = os.urandom(NONCE_BYTES)
        self._wrapped_key = AESGCM(_derive(passphrase, salt, KDF_N, KDF_R, KDF_P)).encrypt(
            self._key_nonce, key, None
        )

    def _set_key_material(self, container: dict) -> None:
        self._salt = _unb64(container["kdf"]["salt"])
        self._kdf = (
            int(container["kdf"]["n"]),
            int(container["kdf"]["r"]),
            int(container["kdf"]["p"]),
        )
        self._key_nonce = _unb64(container["key_nonce"])
        self._wrapped_key = _unb64(container["wrapped_key"])

    def _read_container(self) -> dict:
        try:
            container = json.loads(self.vault_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise PortableVaultError("Portable credential vault is unreadable") from None
        if (
            container.get("version") != VAULT_VERSION
            or container.get("kdf", {}).get("name") != "scrypt"
        ):
            raise PortableVaultError("Unsupported portable credential vault")
        return container

    def _decrypt_payload(self, container: dict, key: bytes) -> dict[str, str]:
        try:
            plaintext = AESGCM(key).decrypt(
                _unb64(container["nonce"]), _unb64(container["ciphertext"]), None
            )
            payload = json.loads(plaintext.decode("utf-8"))
        except Exception:
            raise PortableVaultError("Incorrect passphrase") from None
        if payload.get("version") != VAULT_VERSION or not isinstance(payload.get("secrets"), dict):
            raise PortableVaultError("Unsupported portable credential vault")
        return payload["secrets"]

    def _save_payload(self) -> None:
        if self._key is None:
            raise PortableVaultLocked("Portable credential vault is locked")
        nonce = os.urandom(NONCE_BYTES)
        payload = json.dumps(
            {"version": VAULT_VERSION, "secrets": self._secrets},
            separators=(",", ":"),
        ).encode("utf-8")
        container = {
            "version": VAULT_VERSION,
            "kdf": {
                "name": "scrypt",
                "salt": _b64(self._salt),
                "n": self._kdf[0],
                "r": self._kdf[1],
                "p": self._kdf[2],
            },
            "key_nonce": _b64(self._key_nonce),
            "wrapped_key": _b64(self._wrapped_key),
            "nonce": _b64(nonce),
            "ciphertext": _b64(AESGCM(self._key).encrypt(nonce, payload, None)),
        }
        _atomic_write(self.vault_path, json.dumps(container).encode("utf-8"))

    def _arm_auto_unlock(self) -> None:
        self._auto_unlock = False
        if self._key is None or not self._protector.available():
            return
        try:
            _atomic_write(self.dpapi_path, self._protector.protect(self._key))
            self._auto_unlock = True
        except Exception:
            self.dpapi_path.unlink(missing_ok=True)

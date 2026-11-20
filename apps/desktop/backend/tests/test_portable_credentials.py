import sys
from pathlib import Path

import pytest
from wenyi_core.llm.configuration import ProviderConfig
from wenyi_desktop.local_credentials import CredentialStore, CredentialUnavailable
from wenyi_desktop.main import create_context
from wenyi_desktop.portable_credentials import (
    DpapiProtector,
    PortableVault,
    PortableVaultError,
    PortableVaultLocked,
)

PASSPHRASE = "correct horse battery"
SERVICE = "org.wenyi.desktop"


class FakeProtector:
    def __init__(self) -> None:
        self.values: dict[bytes, bytes] = {}

    def available(self) -> bool:
        return True

    def protect(self, value: bytes) -> bytes:
        wrapped = b"wrapped:" + value
        self.values[wrapped] = value
        return wrapped

    def unprotect(self, value: bytes) -> bytes:
        if value not in self.values:
            raise RuntimeError("not protected by this user")
        return self.values[value]


def test_roundtrip_keeps_secrets_out_of_plaintext(tmp_path: Path) -> None:
    vault = PortableVault(tmp_path, protector=FakeProtector())
    vault.create(PASSPHRASE)
    vault.set_password(SERVICE, "ref-1", "fake-portable-secret")
    assert b"fake-portable-secret" not in (tmp_path / "credentials.vault").read_bytes()
    vault.lock()
    vault.unlock(PASSPHRASE)
    assert vault.get_password(SERVICE, "ref-1") == "fake-portable-secret"


def test_wrong_passphrase_does_not_replace_the_vault(tmp_path: Path) -> None:
    first = PortableVault(tmp_path, protector=FakeProtector())
    first.create(PASSPHRASE)
    first.set_password(SERVICE, "ref-1", "fake-portable-secret")
    contents = (tmp_path / "credentials.vault").read_bytes()
    first.lock()
    second = PortableVault(tmp_path, protector=FakeProtector())
    with pytest.raises(PortableVaultError):
        second.unlock("wrong passphrase")
    assert (tmp_path / "credentials.vault").read_bytes() == contents
    assert not second.unlocked


def test_lock_removes_auto_unlock_and_requires_the_passphrase(tmp_path: Path) -> None:
    protector = FakeProtector()
    vault = PortableVault(tmp_path, protector=protector)
    vault.create(PASSPHRASE)
    assert vault.auto_unlock
    vault.lock()
    assert not vault.auto_unlock
    assert not vault.try_auto_unlock()
    with pytest.raises(PortableVaultLocked):
        vault.get_password(SERVICE, "missing")
    vault.unlock(PASSPHRASE)
    assert vault.auto_unlock


def test_auto_unlock_uses_the_saved_data_key(tmp_path: Path) -> None:
    protector = FakeProtector()
    first = PortableVault(tmp_path, protector=protector)
    first.create(PASSPHRASE)
    first.set_password(SERVICE, "ref-1", "fake-portable-secret")
    second = PortableVault(tmp_path, protector=protector)
    assert second.try_auto_unlock()
    assert second.get_password(SERVICE, "ref-1") == "fake-portable-secret"


def test_auto_unlock_failure_keeps_the_vault_locked(tmp_path: Path) -> None:
    class Broken(FakeProtector):
        def unprotect(self, value: bytes) -> bytes:
            raise RuntimeError("another user")

    first = PortableVault(tmp_path, protector=FakeProtector())
    first.create(PASSPHRASE)
    second = PortableVault(tmp_path, protector=Broken())
    assert not second.try_auto_unlock()
    assert not second.unlocked
    first.lock()
    first.unlock(PASSPHRASE)
    assert first.present


def test_change_passphrase_keeps_existing_secrets(tmp_path: Path) -> None:
    vault = PortableVault(tmp_path, protector=FakeProtector())
    vault.create(PASSPHRASE)
    vault.set_password(SERVICE, "ref-1", "fake-portable-secret")
    vault.change_passphrase(PASSPHRASE, "another correct horse")
    vault.lock()
    with pytest.raises(PortableVaultError):
        vault.unlock(PASSPHRASE)
    vault.unlock("another correct horse")
    assert vault.get_password(SERVICE, "ref-1") == "fake-portable-secret"


def test_passphrase_policy(tmp_path: Path) -> None:
    vault = PortableVault(tmp_path, protector=FakeProtector())
    for value in ("", "short", "has\x00nul"):
        with pytest.raises(PortableVaultError):
            vault.create(value)


def test_second_create_is_refused(tmp_path: Path) -> None:
    vault = PortableVault(tmp_path, protector=FakeProtector())
    vault.create(PASSPHRASE)
    with pytest.raises(PortableVaultError):
        vault.create(PASSPHRASE)


@pytest.mark.skipif(sys.platform != "win32", reason="DPAPI is Windows-only")
def test_dpapi_protector_roundtrip() -> None:
    protector = DpapiProtector()
    assert protector.available()
    assert protector.unprotect(protector.protect(b"fake-secret")) == b"fake-secret"


def provider() -> ProviderConfig:
    return ProviderConfig(kind="openai", api_key_env="WENYI_TEST_FAKE_KEY")


def test_store_persists_portable_credentials(tmp_path: Path) -> None:
    vault = PortableVault(tmp_path, protector=FakeProtector())
    vault.create(PASSPHRASE)
    store = CredentialStore(tmp_path, vault=vault)
    store.update("one", mode="manual", secret="fake-portable-secret")
    record = store._records()["one"]
    assert record["storage"] == "portable"
    assert store.snapshot({"one": provider()})["one"] == "fake-portable-secret"
    assert store.status("one", provider())["storage"] == "portable"


def test_locked_portable_vault_falls_back_to_session(tmp_path: Path) -> None:
    vault = PortableVault(tmp_path, protector=FakeProtector())
    vault.create(PASSPHRASE)
    store = CredentialStore(tmp_path, vault=vault)
    store.update("one", mode="manual", secret="fake-portable-secret")
    vault.lock()
    store.update("two", mode="manual", secret="fake-session-secret")
    assert store._records()["two"]["storage"] == "session"
    assert store.snapshot({"two": provider()})["two"] == "fake-session-secret"
    with pytest.raises(CredentialUnavailable):
        store.update("three", mode="manual", secret="fake-failed", storage="system")


def test_portable_vault_serves_mineru(tmp_path: Path) -> None:
    vault = PortableVault(tmp_path, protector=FakeProtector())
    vault.create(PASSPHRASE)
    store = CredentialStore(tmp_path, vault=vault)
    status = store.save_mineru(secret="fake-mineru-key")
    assert status["storage"] == "portable"
    assert store.resolve_mineru_token() == "fake-mineru-key"


def test_create_context_selects_portable_vault(tmp_path: Path) -> None:
    context = create_context(tmp_path, portable=True, api_token="fake-token")
    try:
        assert context.settings_store.credentials.vault.storage == "portable"
    finally:
        context.repository.close()

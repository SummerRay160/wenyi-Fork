"""Authenticated controls for the fork-only portable credential vault."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, SecretStr, field_validator

from ..local_credentials import credential_store
from ..portable_credentials import PortableVault, PortableVaultError
from .credentials import desktop_only

router = APIRouter(
    prefix="/desktop/portable-credentials",
    tags=["desktop"],
    dependencies=[Depends(desktop_only)],
)


class PortableVaultStatus(BaseModel):
    supported: bool
    present: bool
    unlocked: bool
    auto_unlock: bool


def passphrase_length(value: SecretStr) -> SecretStr:
    text = value.get_secret_value()
    if not 8 <= len(text) <= 1024 or "\x00" in text:
        raise ValueError("Passphrase must be 8 to 1024 characters")
    return value


class PassphraseInput(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    passphrase: SecretStr

    @field_validator("passphrase")
    @classmethod
    def _passphrase(cls, value: SecretStr) -> SecretStr:
        return passphrase_length(value)


class ChangePassphraseInput(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    current: SecretStr
    next: SecretStr

    @field_validator("current", "next")
    @classmethod
    def _passphrase(cls, value: SecretStr) -> SecretStr:
        return passphrase_length(value)


def portable_vault() -> PortableVault | None:
    store = credential_store()
    return store.vault if store.portable else None


def _status(vault: PortableVault | None) -> PortableVaultStatus:
    if vault is None:
        return PortableVaultStatus(
            supported=False,
            present=False,
            unlocked=False,
            auto_unlock=False,
        )
    return PortableVaultStatus(supported=True, **vault.status())


def _require_vault() -> PortableVault:
    vault = portable_vault()
    if vault is None:
        raise HTTPException(400, "This build does not use a portable credential vault")
    return vault


@router.get("", response_model=PortableVaultStatus)
def status(response: Response) -> PortableVaultStatus:
    response.headers["Cache-Control"] = "no-store"
    return _status(portable_vault())


@router.post("/create", response_model=PortableVaultStatus)
async def create(request: Request) -> PortableVaultStatus:
    try:
        body = PassphraseInput.model_validate(await request.json())
    except Exception:
        raise HTTPException(422, "Invalid passphrase request") from None
    vault = _require_vault()
    try:
        await run_in_threadpool(vault.create, body.passphrase.get_secret_value())
    except PortableVaultError as error:
        if vault.present:
            raise HTTPException(409, "Portable credential vault already exists") from None
        raise HTTPException(400, str(error)) from None
    return _status(vault)


@router.post("/unlock", response_model=PortableVaultStatus)
async def unlock(request: Request) -> PortableVaultStatus:
    try:
        body = PassphraseInput.model_validate(await request.json())
    except Exception:
        raise HTTPException(422, "Invalid passphrase request") from None
    vault = _require_vault()
    try:
        await run_in_threadpool(vault.unlock, body.passphrase.get_secret_value())
    except PortableVaultError:
        await run_in_threadpool(time.sleep, 0.25)
        raise HTTPException(400, "Incorrect passphrase") from None
    return _status(vault)


@router.post("/lock", response_model=PortableVaultStatus)
async def lock() -> PortableVaultStatus:
    vault = _require_vault()
    await run_in_threadpool(vault.lock)
    return _status(vault)


@router.post("/passphrase", response_model=PortableVaultStatus)
async def change_passphrase(request: Request) -> PortableVaultStatus:
    try:
        body = ChangePassphraseInput.model_validate(await request.json())
    except Exception:
        raise HTTPException(422, "Invalid passphrase request") from None
    vault = _require_vault()
    try:
        await run_in_threadpool(
            vault.change_passphrase,
            body.current.get_secret_value(),
            body.next.get_secret_value(),
        )
    except PortableVaultError:
        await run_in_threadpool(time.sleep, 0.25)
        raise HTTPException(400, "Incorrect passphrase") from None
    return _status(vault)

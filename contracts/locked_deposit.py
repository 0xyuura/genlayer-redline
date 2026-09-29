# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
"""LockedDeposit: a lock that opens early when the terms it relied on get worse.

It holds no model and no web access. Members deposit under the current version
of one Redline charter and cannot withdraw until their lock expires. The one
exception is the reason the lock was acceptable in the first place: if any
version after the one a member deposited under weakened a term this deposit
watches, the member may leave at once with everything they put in.

The watched terms are fixed at deployment and must exist in the charter. A
member who deposits again after an amendment is taken to accept the terms as
they stand, so their join version moves forward with the new deposit.
"""

import json
import typing
from datetime import datetime, timezone
from genlayer import *

ERROR_EXPECTED = "[EXPECTED]"
_HEX = set("0123456789abcdef")


def address_text(value: typing.Any) -> str:
    text = value if isinstance(value, str) else str(value)
    ok = len(text) == 42 and text[:2] == "0x" and set(text[2:].lower()) <= _HEX
    return text.lower() if ok else ""


def watched_from_input(raw: typing.Any, names: list) -> list:
    if isinstance(raw, str) and raw.strip().startswith("["):
        try:
            raw = json.loads(raw)
        except Exception:
            raise ValueError("WATCHED_NOT_JSON")
    if not isinstance(raw, list):
        raw = [raw]
    out = [str(x) for x in raw]
    if not out or len(set(out)) != len(out):
        raise ValueError("WATCHED_SHAPE")
    for name in out:
        if name not in names:
            raise ValueError("UNKNOWN_TERM")
    return sorted(out)


def exit_reason(now: int, unlock_at: int, weakened: list, watched: list) -> str:
    """Why the member may leave now, or empty string while the lock holds."""
    if now >= unlock_at:
        return "LOCK_EXPIRED"
    hit = sorted(set(weakened) & set(watched))
    if hit:
        return "TERMS_WEAKENED:" + ",".join(hit)
    return ""


def _fail(code: str) -> typing.NoReturn:
    raise gl.vm.UserError(ERROR_EXPECTED + " " + code)


def _now() -> int:
    return int(datetime.now(timezone.utc).timestamp())


@gl.evm.contract_interface
class _Recipient:
    class View:
        pass

    class Write:
        pass


class LockedDeposit(gl.Contract):
    redline: Address
    charter_id: str
    watched: str
    lock_seconds: u256
    balances: TreeMap[str, u256]
    joined: TreeMap[str, u256]
    unlock_at: TreeMap[str, u256]

    def __init__(self, redline: typing.Any, charter_id: str,
                 watched: typing.Any, lock_seconds: typing.Any) -> None:
        self.redline = (redline if isinstance(redline, Address)
                        else Address(str(redline)))
        self.charter_id = str(charter_id)
        charter = json.loads(
            gl.get_contract_at(self.redline).view().get_charter(self.charter_id))
        if charter["state"] != "ACTIVE":
            _fail("CHARTER_NOT_ACTIVE")
        try:
            names = [t["name"] for t in charter["terms"]]
            self.watched = ",".join(watched_from_input(watched, names))
            lock = int(str(lock_seconds))
        except ValueError as err:
            _fail(str(err))
        if lock <= 0:
            _fail("LOCK_RANGE")
        self.lock_seconds = u256(lock)

    @gl.public.write.payable
    def deposit(self) -> int:
        paid = int(gl.message.value)
        if paid == 0:
            _fail("NOTHING_SENT")
        who = address_text(gl.message.sender_address)
        version = int(gl.get_contract_at(self.redline).view().latest(self.charter_id))
        held = int(self.balances[who]) if who in self.balances else 0
        self.balances[who] = u256(held + paid)
        self.joined[who] = u256(version)
        self.unlock_at[who] = u256(_now() + int(self.lock_seconds))
        return version

    @gl.public.write
    def withdraw(self) -> str:
        who = address_text(gl.message.sender_address)
        amount = int(self.balances[who]) if who in self.balances else 0
        if amount == 0:
            _fail("NOTHING_DEPOSITED")
        reason = exit_reason(_now(), int(self.unlock_at[who]),
                             self._weakened(who), str(self.watched).split(","))
        if not reason:
            _fail("LOCKED")
        self.balances[who] = u256(0)
        _Recipient(gl.message.sender_address).emit_transfer(value=u256(amount))
        return reason

    @gl.public.view
    def position(self, who: typing.Any) -> str:
        key = address_text(who)
        if key not in self.balances:
            return json.dumps({"balance": "0"})
        weakened = self._weakened(key)
        return json.dumps({
            "balance": str(int(self.balances[key])),
            "joined": int(self.joined[key]),
            "unlock_at": int(self.unlock_at[key]),
            "weakened_since_join": weakened,
            "exit_open": exit_reason(_now(), int(self.unlock_at[key]), weakened,
                                     str(self.watched).split(",")) != ""},
            sort_keys=True)

    @gl.public.view
    def status(self) -> str:
        return json.dumps({"charter_id": str(self.charter_id),
                           "watched": str(self.watched).split(","),
                           "lock_seconds": int(self.lock_seconds)},
                          sort_keys=True)

    def _weakened(self, who: str) -> list:
        return json.loads(gl.get_contract_at(self.redline).view().weakened_after(
            self.charter_id, int(self.joined[who])))

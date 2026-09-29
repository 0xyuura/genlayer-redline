# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
"""Grandfather: you stay on the terms you agreed to until you agree again.

It holds no model and no web access. A member accepts one Redline charter at
its current version. Amendments that Redline recorded as weakening nothing
carry the member forward automatically, because nothing was taken from them.
The first amendment that weakened any protected term stops that: the member
stays bound by the last version before it until they accept again.

LockedDeposit answers a weakening with exit. This contract answers it with
consent. Both read the same record.
"""

import json
import typing
from genlayer import *

ERROR_EXPECTED = "[EXPECTED]"
_HEX = set("0123456789abcdef")


def address_text(value: typing.Any) -> str:
    text = value if isinstance(value, str) else str(value)
    ok = len(text) == 42 and text[:2] == "0x" and set(text[2:].lower()) <= _HEX
    return text.lower() if ok else ""


def bound_from(versions: list, accepted: int) -> dict:
    """The version a member who accepted `accepted` is bound by, and the first
    later version that weakened something, if any. `versions` is Redline's
    version records in order."""
    bound, blocker = accepted, None
    for v in versions:
        n = int(v["n"])
        if n <= accepted:
            continue
        if v["weakened"]:
            blocker = {"version": n, "weakened": list(v["weakened"])}
            break
        bound = n
    return {"bound": bound, "blocked_by": blocker}


def _fail(code: str) -> typing.NoReturn:
    raise gl.vm.UserError(ERROR_EXPECTED + " " + code)


class Grandfather(gl.Contract):
    redline: Address
    charter_id: str
    accepted: TreeMap[str, u256]
    members: DynArray[str]

    def __init__(self, redline: typing.Any, charter_id: str) -> None:
        self.redline = (redline if isinstance(redline, Address)
                        else Address(str(redline)))
        self.charter_id = str(charter_id)
        charter = json.loads(
            gl.get_contract_at(self.redline).view().get_charter(self.charter_id))
        if charter["state"] != "ACTIVE":
            _fail("CHARTER_NOT_ACTIVE")

    @gl.public.write
    def accept(self) -> int:
        who = address_text(gl.message.sender_address)
        version = int(gl.get_contract_at(self.redline).view().latest(self.charter_id))
        if who not in self.accepted:
            self.members.append(who)
        self.accepted[who] = u256(version)
        return version

    @gl.public.view
    def binding(self, who: typing.Any) -> str:
        key = address_text(who)
        if key not in self.accepted:
            _fail("NOT_A_MEMBER")
        accepted = int(self.accepted[key])
        out = bound_from(self._versions(), accepted)
        out["accepted"] = accepted
        out["source"] = json.loads(gl.get_contract_at(self.redline).view()
                                   .get_version(self.charter_id, out["bound"]))["source"]
        return json.dumps(out, sort_keys=True)

    @gl.public.view
    def status(self) -> str:
        return json.dumps({"charter_id": str(self.charter_id),
                           "members": {str(m): int(self.accepted[m])
                                       for m in self.members}},
                          sort_keys=True)

    def _versions(self) -> list:
        view = gl.get_contract_at(self.redline).view()
        latest = int(view.latest(self.charter_id))
        return [json.loads(view.get_version(self.charter_id, n))
                for n in range(1, latest + 1)]

# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
"""Network probe (test only). It measures what LaunchClaimBounties relies on:
the time a contract sees for a transaction, what happens to GEN sent with a
call that fails, and what web.render returns for a table, a missing page and
a redirect. It holds no logic of its own."""
import hashlib
import json
from genlayer import *


class Probe(gl.Contract):
    log: TreeMap[str, str]
    n: u256

    def __init__(self):
        self.n = u256(0)

    def _add(self, what: str) -> None:
        self.n = u256(int(self.n) + 1)
        self.log[str(int(self.n))] = json.dumps({"what": what, "datetime": str(gl.message_raw["datetime"]), "value": str(int(gl.message.value))})

    @gl.public.write
    def stamp(self, tag: str) -> str:
        """Not payable. Stores the transaction time the contract sees."""
        self._add("stamp:" + tag)
        return str(gl.message_raw["datetime"])

    @gl.public.write.payable
    def pay_ok(self) -> str:
        self._add("pay_ok")
        return "ok"

    @gl.public.write.payable
    def pay_raise(self) -> str:
        raise gl.vm.UserError("refused on purpose")

    @gl.public.write
    def digest(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    @gl.public.write
    def look(self, url: str) -> dict:
        """What web.render gives for a page: its text (first 1,500 characters), or the error."""
        def leader() -> dict:
            try:
                t = gl.nondet.web.render(url, mode="text", wait_after_loaded="4s")
                if isinstance(t, (bytes, bytearray)):
                    t = bytes(t).decode("utf-8", errors="replace")
                return {"ok": True, "length": len(t), "text": str(t)[:1500]}
            except Exception as e:
                return {"ok": False, "length": -1, "text": str(e)[:300]}

        def validator(res) -> bool:
            return isinstance(res, gl.vm.Return)

        out = gl.vm.run_nondet_unsafe(leader, validator)
        self._add("look")
        return out

    @gl.public.view
    def get_log(self) -> list:
        return [json.loads(self.log[str(i)]) for i in range(1, int(self.n) + 1)]

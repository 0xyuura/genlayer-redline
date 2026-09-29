"""Offline suite for Redline. No network, no model, no chain.

Every rule that decides anything is a module level pure function, so most of
this file calls them directly: the immutable source rule, the terms parser,
the label rule validators compare, who may propose, what has been weakened
since a version, the prompt fences, and both consumers' decisions.

The contract classes are also driven end to end with plain dicts standing in
for storage, a patched fetch and a patched model. The nondet block runs the
leader and then hands its result to the validator, so every baseline check and
review here also checks that an honest validator agrees.

The mutations at the end prove the suite notices when a rule is removed.
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _stub

_stub.install()

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "contracts"))

import redline as R
import locked_deposit as D
import grandfather as G

SHA = "0123456789abcdef0123456789abcdef01234567"
BASE = "https://raw.githubusercontent.com/0xyuura/genlayer-redline/" + SHA
V1, V2, V3 = (BASE + "/examples/terms-v%d.md" % i for i in (1, 2, 3))
OPERATOR = "0x" + "a1" * 20
MEMBER = "0x" + "b0" * 20
OTHER = "0x" + "c4" * 20

TERMS = [
    {"name": "refund_window",
     "text": "Customers may request a full refund within 30 days of purchase."},
    {"name": "data_export",
     "text": "Customers can export all of their data at any time."},
    {"name": "price_notice",
     "text": "Customers are notified at least 14 days before any price increase."},
]
NAMES = [t["name"] for t in TERMS]


def labels(**kw):
    return {"labels": kw}


class Sources(unittest.TestCase):
    def test_pinned_github_accepted(self):
        self.assertEqual(R.source_from_input(V1), V1)

    def test_mutable_sources_refused(self):
        for bad in (V1.replace(SHA, "main"), V1 + "?x", V1 + "#a",
                    V1.replace("examples/", "examples//"),
                    V1.replace("https://", "http://"),
                    "https://example.com/terms.md", BASE + "/docs/"):
            with self.assertRaises(ValueError, msg=bad):
                R.source_from_input(bad)


class Terms(unittest.TestCase):
    def test_parses_and_normalises(self):
        raw = [{"name": "refund_window", "text": "  a \n b "}]
        self.assertEqual(R.terms_from_input(raw),
                         [{"name": "refund_window", "text": "a b"}])
        self.assertEqual(R.terms_from_input(json.dumps(TERMS)), TERMS)

    def test_limits(self):
        many = [{"name": "t%d" % i, "text": "x"} for i in range(R.MAX_TERMS)]
        self.assertEqual(len(R.terms_from_input(many)), R.MAX_TERMS)
        cases = (
            ("not json", "TERMS_NOT_JSON"),
            ([], "TERMS_SHAPE"),
            (many + [{"name": "t99", "text": "x"}], "TERMS_SHAPE"),
            ({"name": "a", "text": "b"}, "TERMS_SHAPE"),
            ([{"name": "a"}], "TERM_KEYS"),
            ([{"name": "a", "text": "b", "weight": 1}], "TERM_KEYS"),
            ([{"name": "Refund", "text": "b"}], "TERM_NAME"),
            ([{"name": "_hidden", "text": "b"}], "TERM_NAME"),
            ([{"name": "a-b", "text": "b"}], "TERM_NAME"),
            ([{"name": "x" * 33, "text": "b"}], "TERM_NAME"),
            ([{"name": "a", "text": "b"}, {"name": "a", "text": "c"}], "TERM_DUP"),
            ([{"name": "a", "text": "   "}], "TERM_TEXT"),
            ([{"name": "a", "text": "x" * 301}], "TERM_TEXT"),
            ([{"name": "a", "text": 5}], "TERM_TEXT"),
        )
        for raw, code in cases:
            with self.assertRaises(ValueError, msg=code) as ctx:
                R.terms_from_input(raw)
            self.assertEqual(str(ctx.exception), code)

    def test_title(self):
        self.assertEqual(R.check_title("  Lanternbox   terms "), "Lanternbox terms")
        for bad, code in (("", "TITLE_LENGTH"), ("x" * 81, "TITLE_LENGTH"),
                          (None, "TITLE_TYPE")):
            with self.assertRaises(ValueError) as ctx:
                R.check_title(bad)
            self.assertEqual(str(ctx.exception), code)


class Labels(unittest.TestCase):
    def test_exact_shape_sorted(self):
        reply = labels(refund_window="WEAKENED", price_notice="KEPT",
                       data_export="KEPT")
        got = R.labels_from_reply(reply, NAMES, R.REVIEW_LABELS)
        self.assertEqual(list(got), sorted(NAMES))
        self.assertEqual(R.labels_from_reply(json.dumps(reply), NAMES,
                                             R.REVIEW_LABELS), got)
        self.assertEqual(R.names_with(got, "WEAKENED"), ["refund_window"])

    def test_same_answer_in_any_order_is_the_same_string(self):
        a = R.canonical(R.labels_from_reply(
            labels(refund_window="KEPT", data_export="KEPT", price_notice="KEPT"),
            NAMES, R.REVIEW_LABELS))
        b = R.canonical(R.labels_from_reply(
            labels(price_notice="KEPT", refund_window="KEPT", data_export="KEPT"),
            NAMES, R.REVIEW_LABELS))
        self.assertEqual(a, b)

    def test_rejections(self):
        full = dict(refund_window="KEPT", data_export="KEPT", price_notice="KEPT")
        cases = (
            ("nope", "REPLY_NOT_JSON"),
            ([], "REPLY_SHAPE"),
            ({"labels": full, "why": "x"}, "REPLY_SHAPE"),
            ({"labels": []}, "REPLY_TERMS"),
            ({"labels": dict(full, extra="KEPT")}, "REPLY_TERMS"),
            ({"labels": {"refund_window": "KEPT"}}, "REPLY_TERMS"),
            ({"labels": dict(full, refund_window="kept")}, "UNKNOWN_LABEL"),
            ({"labels": dict(full, refund_window="STATED")}, "UNKNOWN_LABEL"),
            ({"labels": dict(full, refund_window="UNCLEAR")}, "UNKNOWN_LABEL"),
        )
        for reply, code in cases:
            with self.assertRaises(ValueError, msg=code) as ctx:
                R.labels_from_reply(reply, NAMES, R.REVIEW_LABELS)
            self.assertEqual(str(ctx.exception), code)

    def test_baseline_and_review_sets_do_not_mix(self):
        with self.assertRaises(ValueError):
            R.labels_from_reply(labels(refund_window="KEPT", data_export="KEPT",
                                       price_notice="KEPT"),
                                NAMES, R.BASELINE_LABELS)


class Rules(unittest.TestCase):
    def test_may_propose(self):
        ok = dict(state="ACTIVE", operator=OPERATOR, sender=OPERATOR,
                  pending="", current=V1, source=V2)
        self.assertEqual(R.may_propose(**ok), "")
        self.assertEqual(R.may_propose(**dict(ok, sender=OPERATOR.upper()
                                              .replace("0X", "0x"))), "")
        for change, code in ((dict(sender=OTHER), "NOT_OPERATOR"),
                             (dict(state="PENDING_BASELINE"), "NOT_ACTIVE"),
                             (dict(state="REJECTED"), "NOT_ACTIVE"),
                             (dict(pending=V3), "PROPOSAL_PENDING"),
                             (dict(source=V1), "SAME_SOURCE")):
            self.assertEqual(R.may_propose(**dict(ok, **change)), code)

    def test_weakened_since(self):
        log = [{"n": 1, "weakened": []}, {"n": 2, "weakened": []},
               {"n": 3, "weakened": ["refund_window"]},
               {"n": 4, "weakened": ["data_export", "refund_window"]}]
        self.assertEqual(R.weakened_since(log, 1), ["data_export", "refund_window"])
        self.assertEqual(R.weakened_since(log, 3), ["data_export", "refund_window"])
        self.assertEqual(R.weakened_since(log, 2), ["data_export", "refund_window"])
        self.assertEqual(R.weakened_since(log[:3], 3), [])
        self.assertEqual(R.weakened_since(log, 4), [])


class Prompts(unittest.TestCase):
    def test_review_prompt_fences_everything(self):
        p = R.review_prompt(TERMS, "OLD BODY", "NEW BODY")
        tag = R._fence(R._terms_block(TERMS), "OLD BODY", "NEW BODY")
        for label in ("terms", "old", "new"):
            self.assertIn("<" + label + " " + tag + ">", p)
            self.assertIn("</" + label + " " + tag + ">", p)
        self.assertLess(p.index("OLD BODY"), p.index("NEW BODY"))
        for t in TERMS:
            self.assertIn(t["name"] + ": " + t["text"], p)
        self.assertIn("KEPT", p)
        self.assertIn("WEAKENED", p)
        self.assertIn("unclear", p)

    def test_baseline_prompt(self):
        p = R.baseline_prompt(TERMS, "DOC")
        self.assertIn("NOT_STATED", p)
        self.assertIn("\nDOC\n", p)

    def test_tag_depends_on_every_input(self):
        base = R._fence("a", "b", "c")
        self.assertNotEqual(base, R._fence("a", "b", "d"))
        self.assertNotEqual(base, R._fence("a", "c", "b"))

    def test_collision_refused(self):
        orig = R._fence
        try:
            R._fence = lambda *p: "feedfacefeedface"
            for args in ((TERMS, "has feedfacefeedface", "new"),
                         (TERMS, "old", "feedfacefeedface")):
                with self.assertRaises(ValueError) as ctx:
                    R.review_prompt(*args)
                self.assertEqual(str(ctx.exception), "FENCE_COLLISION")
            with self.assertRaises(ValueError):
                R.baseline_prompt(TERMS, "x feedfacefeedface")
        finally:
            R._fence = orig


class _Res:
    def __init__(self, body, status=200):
        self.body = body
        self.status_code = status


DOCS = {V1: b"refund 30 days; export anytime; 14 days notice",
        V2: b"reworded: refund 30 days; export anytime; 14 days notice",
        V3: b"refund 7 days; export anytime; 14 days notice"}


class Harness(unittest.TestCase):
    def setUp(self):
        self.fetched, self.prompts = [], []
        self.status = 200
        self.baseline = labels(refund_window="STATED", data_export="STATED",
                               price_notice="STATED")
        self.review_reply = labels(refund_window="KEPT", data_export="KEPT",
                                   price_notice="KEPT")
        self.saved = (R._now, R.gl.nondet.web.request, R.gl.nondet.exec_prompt,
                      R.gl.vm.run_nondet_unsafe)
        R._now = lambda: 1_800_000_000

        def request(url, method="GET"):
            self.fetched.append(url)
            return _Res(DOCS.get(url, b""), self.status)

        def prompt(text, response_format=None):
            self.prompts.append(text)
            return self.review_reply if "<old " in text else self.baseline

        def both(leader, validator):
            out = leader()
            if not validator(R.gl.vm.Return(out)):
                raise AssertionError("an honest validator disagreed")
            return out

        R.gl.nondet.web.request = request
        R.gl.nondet.exec_prompt = prompt
        R.gl.vm.run_nondet_unsafe = both
        self.c = R.Redline()
        self.c.charters, self.c.charter_ids, self.c.version_log = {}, [], {}

    def tearDown(self):
        (R._now, R.gl.nondet.web.request, R.gl.nondet.exec_prompt,
         R.gl.vm.run_nondet_unsafe) = self.saved
        R.gl.message.sender_address = "0x" + "11" * 20

    def as_(self, who):
        R.gl.message.sender_address = who

    def code(self, fn, *args):
        with self.assertRaises(R.gl.vm.UserError) as ctx:
            fn(*args)
        return ctx.exception.message

    def charter(self, rid="r1"):
        return json.loads(self.c.get_charter(rid))

    def active(self):
        self.as_(OPERATOR)
        rid = self.c.register("Lanternbox terms", TERMS, V1)
        self.as_(OTHER)
        self.assertEqual(self.c.confirm_baseline(rid), "ACTIVE")
        self.fetched.clear()
        self.prompts.clear()
        return rid

    def amend(self, rid, url, **reply):
        self.as_(OPERATOR)
        self.c.propose(rid, url)
        self.review_reply = labels(**reply)
        self.as_(OTHER)
        return json.loads(self.c.review(rid))


KEEP_ALL = dict(refund_window="KEPT", data_export="KEPT", price_notice="KEPT")


class Registering(Harness):
    def test_register_records_operator_and_waits(self):
        self.as_(OPERATOR)
        self.assertEqual(self.c.register("Lanternbox terms", json.dumps(TERMS), V1), "r1")
        got = self.charter()
        self.assertEqual((got["operator"], got["state"], got["versions"]),
                         (OPERATOR, "PENDING_BASELINE", 0))
        self.assertEqual(got["terms"], TERMS)
        self.assertEqual(self.fetched, [])

    def test_register_refusals(self):
        self.as_(OPERATOR)
        self.assertEqual(self.code(self.c.register, "t", TERMS,
                                   V1.replace(SHA, "main")),
                         "[EXPECTED] SOURCE_NOT_IMMUTABLE")
        self.assertEqual(self.code(self.c.register, "t", [], V1),
                         "[EXPECTED] TERMS_SHAPE")
        self.assertEqual(self.code(self.c.register, "", TERMS, V1),
                         "[EXPECTED] TITLE_LENGTH")
        self.assertEqual(self.c.charter_ids, [])

    def test_baseline_activates_and_records_version_one(self):
        rid = self.active()
        got = self.charter(rid)
        self.assertEqual((got["state"], got["versions"], got["current"]),
                         ("ACTIVE", 1, V1))
        v1 = json.loads(self.c.get_version(rid, 1))
        self.assertEqual((v1["source"], v1["weakened"]), (V1, []))
        self.assertEqual(self.code(self.c.confirm_baseline, rid),
                         "[EXPECTED] NOT_PENDING_BASELINE")

    def test_baseline_rejects_a_term_the_document_does_not_state(self):
        self.baseline = labels(refund_window="STATED", data_export="NOT_STATED",
                               price_notice="NOT_STATED")
        self.as_(OPERATOR)
        rid = self.c.register("Lanternbox terms", TERMS, V1)
        self.assertEqual(self.c.confirm_baseline(rid), "REJECTED")
        got = self.charter(rid)
        self.assertEqual((got["state"], got["missing"], got["versions"]),
                         ("REJECTED", ["data_export", "price_notice"], 0))
        self.as_(OPERATOR)
        self.assertEqual(self.code(self.c.propose, rid, V2), "[EXPECTED] NOT_ACTIVE")

    def test_baseline_failures_change_nothing(self):
        self.as_(OPERATOR)
        rid = self.c.register("Lanternbox terms", TERMS, V1)
        self.status = 404
        self.assertEqual(self.code(self.c.confirm_baseline, rid),
                         "[EXTERNAL] SOURCE_UNREACHABLE")
        self.status = 200
        self.baseline = labels(refund_window="STATED")
        self.assertEqual(self.code(self.c.confirm_baseline, rid),
                         "[LLM_ERROR] REPLY_TERMS")
        self.assertEqual(self.charter(rid)["state"], "PENDING_BASELINE")


class Proposing(Harness):
    def test_only_the_operator(self):
        rid = self.active()
        for who in (MEMBER, OTHER):
            self.as_(who)
            self.assertEqual(self.code(self.c.propose, rid, V2),
                             "[EXPECTED] NOT_OPERATOR")
        self.as_(OPERATOR)
        self.assertEqual(self.code(self.c.propose, rid, V1), "[EXPECTED] SAME_SOURCE")
        self.assertEqual(self.code(self.c.propose, rid, V2 + "?v=2"),
                         "[EXPECTED] SOURCE_NOT_IMMUTABLE")
        self.c.propose(rid, V2)
        self.assertEqual(self.charter(rid)["pending"], V2)
        self.assertEqual(self.code(self.c.propose, rid, V3),
                         "[EXPECTED] PROPOSAL_PENDING")

    def test_cancel(self):
        rid = self.active()
        self.as_(OPERATOR)
        self.assertEqual(self.code(self.c.cancel, rid), "[EXPECTED] NO_PROPOSAL")
        self.c.propose(rid, V2)
        self.as_(OTHER)
        self.assertEqual(self.code(self.c.cancel, rid), "[EXPECTED] NOT_OPERATOR")
        self.as_(OPERATOR)
        self.c.cancel(rid)
        self.assertEqual(self.charter(rid)["pending"], "")
        self.assertEqual(self.charter(rid)["versions"], 1)


class Reviewing(Harness):
    def test_benign_then_adverse(self):
        rid = self.active()
        out = self.amend(rid, V2, **KEEP_ALL)
        self.assertEqual(out, {"version": 2, "weakened": []})
        out = self.amend(rid, V3, **dict(KEEP_ALL, refund_window="WEAKENED"))
        self.assertEqual(out, {"version": 3, "weakened": ["refund_window"]})
        got = self.charter(rid)
        self.assertEqual((got["current"], got["pending"], got["versions"]),
                         (V3, "", 3))
        self.assertEqual(json.loads(self.c.weakened_after(rid, 1)), ["refund_window"])
        self.assertEqual(json.loads(self.c.weakened_after(rid, 2)), ["refund_window"])
        self.assertEqual(json.loads(self.c.weakened_after(rid, 3)), [])
        self.assertEqual(self.c.latest(rid), 3)

    def test_review_reads_old_then_new_twice(self):
        rid = self.active()
        self.amend(rid, V2, **KEEP_ALL)
        self.assertEqual(self.fetched, [V1, V2, V1, V2])   # leader, validator
        p = self.prompts[0]
        self.assertLess(p.index(DOCS[V1].decode()), p.index(DOCS[V2].decode()))

    def test_review_takes_no_input_and_needs_a_proposal(self):
        rid = self.active()
        self.as_(OTHER)
        self.assertEqual(self.code(self.c.review, rid), "[EXPECTED] NO_PROPOSAL")
        self.assertEqual(self.fetched, [])

    def test_failures_change_nothing(self):
        rid = self.active()
        self.as_(OPERATOR)
        self.c.propose(rid, V2)
        self.status = 500
        self.assertEqual(self.code(self.c.review, rid),
                         "[EXTERNAL] SOURCE_UNREACHABLE")
        self.status = 200
        self.review_reply = labels(**dict(KEEP_ALL, refund_window="UNCLEAR"))
        self.assertEqual(self.code(self.c.review, rid), "[LLM_ERROR] UNKNOWN_LABEL")
        got = self.charter(rid)
        self.assertEqual((got["current"], got["pending"], got["versions"]),
                         (V1, V2, 1))

    def test_validator_rejects_a_different_vector(self):
        rid = self.active()
        self.as_(OPERATOR)
        self.c.propose(rid, V3)
        answers = iter([labels(**KEEP_ALL),
                        labels(**dict(KEEP_ALL, refund_window="WEAKENED"))])
        R.gl.nondet.exec_prompt = lambda *a, **k: next(answers)
        with self.assertRaises(AssertionError):
            self.c.review(rid)

    def test_unknown_ids(self):
        self.assertEqual(self.code(self.c.get_charter, "r9"),
                         "[EXPECTED] NO_SUCH_CHARTER")
        rid = self.active()
        self.assertEqual(self.code(self.c.get_version, rid, 5),
                         "[EXPECTED] NO_SUCH_VERSION")

    def test_counts(self):
        self.active()
        self.baseline = labels(refund_window="NOT_STATED", data_export="STATED",
                               price_notice="STATED")
        self.as_(OPERATOR)
        self.c.confirm_baseline(self.c.register("Other", TERMS, V1))
        self.assertEqual(json.loads(self.c.counts()),
                         {"charters": 2, "by_state": {"ACTIVE": 1, "REJECTED": 1}})


class DepositRules(unittest.TestCase):
    def test_exit_reason(self):
        watched = ["refund_window"]
        self.assertEqual(D.exit_reason(10, 20, [], watched), "")
        self.assertEqual(D.exit_reason(10, 20, ["price_notice"], watched), "")
        self.assertEqual(D.exit_reason(10, 20, ["refund_window", "price_notice"],
                                       watched), "TERMS_WEAKENED:refund_window")
        self.assertEqual(D.exit_reason(20, 20, [], watched), "LOCK_EXPIRED")

    def test_watched(self):
        self.assertEqual(D.watched_from_input('["data_export","refund_window"]', NAMES),
                         ["data_export", "refund_window"])
        self.assertEqual(D.watched_from_input("refund_window", NAMES), ["refund_window"])
        for bad, code in (([], "WATCHED_SHAPE"),
                          (["refund_window", "refund_window"], "WATCHED_SHAPE"),
                          (["nonexistent"], "UNKNOWN_TERM")):
            with self.assertRaises(ValueError) as ctx:
                D.watched_from_input(bad, NAMES)
            self.assertEqual(str(ctx.exception), code)


class GrandfatherRules(unittest.TestCase):
    LOG = [{"n": 1, "weakened": []}, {"n": 2, "weakened": []},
           {"n": 3, "weakened": ["refund_window"]}, {"n": 4, "weakened": []}]

    def test_benign_amendments_carry_you_forward(self):
        self.assertEqual(G.bound_from(self.LOG[:2], 1),
                         {"bound": 2, "blocked_by": None})

    def test_the_first_weakening_stops_you(self):
        self.assertEqual(G.bound_from(self.LOG, 1),
                         {"bound": 2, "blocked_by": {"version": 3,
                                                    "weakened": ["refund_window"]}})

    def test_accepting_again_moves_you_past_it(self):
        self.assertEqual(G.bound_from(self.LOG, 3), {"bound": 4, "blocked_by": None})


class _Redline:
    """What the consumers see of Redline: its views, over a version list."""

    def __init__(self):
        self.log = [{"n": 1, "source": V1, "weakened": []}]

    def view(self):
        return self

    def get_charter(self, rid):
        return json.dumps({"state": "ACTIVE", "terms": TERMS})

    def latest(self, rid):
        return len(self.log)

    def get_version(self, rid, n):
        return json.dumps(self.log[int(n) - 1])

    def weakened_after(self, rid, n):
        return json.dumps(R.weakened_since(self.log, int(n)))


class Consumers(unittest.TestCase):
    def setUp(self):
        self.chain = _Redline()
        self.saved = (getattr(D.gl, "get_contract_at", None), D._now)
        D.gl.get_contract_at = lambda addr: self.chain
        self.clock = 1_800_000_000
        D._now = lambda: self.clock
        D._Recipient.sent.clear()

    def tearDown(self):
        D.gl.get_contract_at, D._now = self.saved
        D.gl.message.sender_address = "0x" + "11" * 20
        D.gl.message.value = 0

    def deposit_contract(self, watched=("refund_window",)):
        d = D.LockedDeposit("0x" + "0f" * 20, "r1", list(watched), 30 * 86400)
        d.balances, d.joined, d.unlock_at = {}, {}, {}
        return d

    def pay(self, d, who, value):
        D.gl.message.sender_address, D.gl.message.value = who, value
        return d.deposit()

    def withdraw(self, d, who):
        D.gl.message.sender_address, D.gl.message.value = who, 0
        return d.withdraw()

    def test_lock_holds_until_a_watched_term_is_weakened(self):
        d = self.deposit_contract()
        self.assertEqual(self.pay(d, MEMBER, 1000), 1)
        with self.assertRaises(D.gl.vm.UserError) as ctx:
            self.withdraw(d, MEMBER)
        self.assertEqual(ctx.exception.message, "[EXPECTED] LOCKED")
        self.chain.log.append({"n": 2, "source": V2, "weakened": []})
        with self.assertRaises(D.gl.vm.UserError):
            self.withdraw(d, MEMBER)
        self.chain.log.append({"n": 3, "source": V3, "weakened": ["refund_window"]})
        self.assertEqual(self.withdraw(d, MEMBER), "TERMS_WEAKENED:refund_window")
        self.assertEqual(D._Recipient.sent, [(MEMBER, 1000)])
        with self.assertRaises(D.gl.vm.UserError) as ctx:
            self.withdraw(d, MEMBER)
        self.assertEqual(ctx.exception.message, "[EXPECTED] NOTHING_DEPOSITED")

    def test_an_unwatched_weakening_keeps_the_lock(self):
        d = self.deposit_contract(("data_export",))
        self.pay(d, MEMBER, 1000)
        self.chain.log.append({"n": 2, "source": V3, "weakened": ["refund_window"]})
        with self.assertRaises(D.gl.vm.UserError):
            self.withdraw(d, MEMBER)
        self.clock += 30 * 86400
        self.assertEqual(self.withdraw(d, MEMBER), "LOCK_EXPIRED")

    def test_depositing_after_an_amendment_accepts_it(self):
        d = self.deposit_contract()
        self.chain.log.append({"n": 2, "source": V3, "weakened": ["refund_window"]})
        self.assertEqual(self.pay(d, MEMBER, 1000), 2)
        with self.assertRaises(D.gl.vm.UserError):
            self.withdraw(d, MEMBER)
        pos = json.loads(d.position(MEMBER))
        self.assertEqual((pos["joined"], pos["exit_open"]), (2, False))

    def test_constructor_policy(self):
        with self.assertRaises(D.gl.vm.UserError) as ctx:
            D.LockedDeposit("0x" + "0f" * 20, "r1", ["nope"], 60)
        self.assertEqual(ctx.exception.message, "[EXPECTED] UNKNOWN_TERM")
        with self.assertRaises(D.gl.vm.UserError) as ctx:
            D.LockedDeposit("0x" + "0f" * 20, "r1", ["refund_window"], 0)
        self.assertEqual(ctx.exception.message, "[EXPECTED] LOCK_RANGE")
        with self.assertRaises(D.gl.vm.UserError) as ctx:
            self.pay(self.deposit_contract(), MEMBER, 0)
        self.assertEqual(ctx.exception.message, "[EXPECTED] NOTHING_SENT")

    def test_grandfather(self):
        g = G.Grandfather("0x" + "0f" * 20, "r1")
        g.accepted, g.members = {}, []
        G.gl.message.sender_address = MEMBER
        self.assertEqual(g.accept(), 1)
        self.chain.log.append({"n": 2, "source": V2, "weakened": []})
        self.chain.log.append({"n": 3, "source": V3, "weakened": ["refund_window"]})
        got = json.loads(g.binding(MEMBER))
        self.assertEqual((got["accepted"], got["bound"], got["source"]), (1, 2, V2))
        self.assertEqual(got["blocked_by"], {"version": 3, "weakened": ["refund_window"]})
        self.assertEqual(g.accept(), 3)
        got = json.loads(g.binding(MEMBER))
        self.assertEqual((got["bound"], got["blocked_by"]), (3, None))
        self.assertEqual(json.loads(g.status())["members"], {MEMBER: 3})
        with self.assertRaises(G.gl.vm.UserError) as ctx:
            g.binding(OTHER)
        self.assertEqual(ctx.exception.message, "[EXPECTED] NOT_A_MEMBER")


class Mutations(unittest.TestCase):
    """Each rule removed in turn; the pinned behaviour must change."""

    def test_silence_as_kept_mutant_is_caught(self):
        # A mutant that fills in missing terms as KEPT lets a new version drop
        # a protection simply by not mentioning it to the model.
        def mutant(reply, names, allowed):
            got = dict(reply["labels"])
            for n in names:
                got.setdefault(n, "KEPT")
            return {n: got[n] for n in sorted(names)}
        partial = labels(data_export="KEPT", price_notice="KEPT")
        self.assertEqual(mutant(partial, NAMES, R.REVIEW_LABELS)["refund_window"], "KEPT")
        with self.assertRaises(ValueError):
            R.labels_from_reply(partial, NAMES, R.REVIEW_LABELS)

    def test_open_propose_mutant_is_caught(self):
        def mutant(state, operator, sender, pending, current, source):
            return "" if state == "ACTIVE" and not pending else "X"
        self.assertEqual(mutant("ACTIVE", OPERATOR, OTHER, "", V1, V2), "")
        self.assertEqual(R.may_propose("ACTIVE", OPERATOR, OTHER, "", V1, V2),
                         "NOT_OPERATOR")

    def test_off_by_one_mutant_is_caught(self):
        log = [{"n": 1, "weakened": []}, {"n": 2, "weakened": ["refund_window"]}]

        def mutant(versions, after):
            return sorted({w for v in versions if int(v["n"]) > after + 1
                           for w in v["weakened"]})
        self.assertEqual(mutant(log, 1), [])
        self.assertEqual(R.weakened_since(log, 1), ["refund_window"])

    def test_grandfather_rolling_past_a_weakening_is_caught(self):
        log = GrandfatherRules.LOG

        def mutant(versions, accepted):
            return {"bound": max(int(v["n"]) for v in versions), "blocked_by": None}
        self.assertEqual(mutant(log, 1)["bound"], 4)
        self.assertEqual(G.bound_from(log, 1)["bound"], 2)

    def test_deposit_ignoring_watch_list_is_caught(self):
        def mutant(now, unlock_at, weakened, watched):
            return "TERMS_WEAKENED" if weakened else D.exit_reason(
                now, unlock_at, [], watched)
        self.assertEqual(mutant(1, 2, ["price_notice"], ["refund_window"]),
                         "TERMS_WEAKENED")
        self.assertEqual(D.exit_reason(1, 2, ["price_notice"], ["refund_window"]), "")


if __name__ == "__main__":
    unittest.main()

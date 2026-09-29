# Redline

**Consensus on what an amendment took away, not on what the terms say.**

Live on Testnet Bradbury at
[`0x0c9858299DF2d108C89c2846e11729f24134da53`](https://explorer-bradbury.genlayer.com/address/0x0c9858299DF2d108C89c2846e11729f24134da53).
Two consumer contracts with opposite answers read the same amendment history;
see [Exercised on chain](#exercised-on-chain).

Call it without a local setup:
[open it in GenLayer Studio](https://studio.genlayer.com/?import-contract=0x0c9858299DF2d108C89c2846e11729f24134da53)

## The problem

Terms change. Services rewrite their terms of service, protocols amend their
charters, licences get new versions. People agreed to one version and are
rarely asked about the next. The question that matters is not what the new
version says. It is what it no longer promises, and to whom.

Every earlier primitive of this kind judges one document. That answers "does
version 3 grant a refund", not "did version 3 take something away from the
people who agreed to version 1", and it has to be asked again, with a model,
every time someone wants to know.

## The move

An operator registers a **charter**: a document at an immutable URL (a GitHub
file pinned to a commit SHA, an IPFS CID or an Arweave id) and one to eight
**protected terms**, written from the reader's side:

```json
[{"name": "refund_window", "text": "Customers may request a full refund within 30 days of purchase."},
 {"name": "data_export",   "text": "Customers can export all of their data at any time."},
 {"name": "price_notice",  "text": "Customers are notified at least 14 days before any price increase."}]
```

1. **Baseline.** Consensus confirms the document states every term
   (`STATED` or `NOT_STATED`). A charter protecting a promise its document
   never makes is `REJECTED`.
2. **Amendment.** Only the operator may propose a new version. Anyone may
   trigger the review, which takes the id and nothing else.
3. **Review.** Validators refetch both versions and agree, exactly, on one
   label per term: `KEPT` or `WEAKENED`. Unclear counts as `WEAKENED`, so the
   burden is on the operator.
4. **History.** Every version is stored with the terms it weakened, forever.
   `weakened_after(id, n)` tells any contract what has been taken from someone
   who agreed to version `n`, with no model call.

What validators compare:

```json
{"data_export": "KEPT", "price_notice": "KEPT", "refund_window": "WEAKENED"}
```

## Who may write

| Write | Who | Policy |
| --- | --- | --- |
| `register` | anyone | the sender becomes the operator, fixed forever |
| `confirm_baseline` | anyone | id only, only while pending |
| `propose` | the operator | one pending proposal, immutable URL, not the current one |
| `cancel` | the operator | withdraws a pending proposal, records nothing |
| `review` | anyone | id only; compares the stored current and pending versions |

Protected terms cannot be added or changed after registration.

## Two consumers, opposite answers

| Consumer | A weakening means |
| --- | --- |
| `LockedDeposit` | **exit**: a weakened term it watches opens your lock early, and you leave with your deposit |
| `Grandfather` | **consent**: you stay bound by the last version before the weakening until you accept again |

Neither calls a model. Full argument in [docs/DESIGN.md](docs/DESIGN.md);
interface in [docs/INTEGRATING.md](docs/INTEGRATING.md).

## Exercised on chain

All verified byte identical to the files here with `genlayer code`:

| Contract | Address |
| --- | --- |
| `Redline` | [`0x0c9858299DF2d108C89c2846e11729f24134da53`](https://explorer-bradbury.genlayer.com/address/0x0c9858299DF2d108C89c2846e11729f24134da53) |
| `LockedDeposit` | [`0x2A8B911B233B99d79c8e2327e6Fb1252ce94d1EE`](https://explorer-bradbury.genlayer.com/address/0x2A8B911B233B99d79c8e2327e6Fb1252ce94d1EE) |
| `Grandfather` | [`0xE9A91581Dc32543c5a6e402F1a6436d318142aB0`](https://explorer-bradbury.genlayer.com/address/0xE9A91581Dc32543c5a6e402F1a6436d318142aB0) |

An operator `0x6ab9...d72c` and a member `0xfb33...a67d`. The document is a
fictional terms of service in [examples/](examples), pinned at commit
`5209cd0`:
[v1](https://raw.githubusercontent.com/0xyuura/genlayer-redline/5209cd09de90e7e25e3b693d1f4ea5305915ad4e/examples/terms-v1.md),
[v2](https://raw.githubusercontent.com/0xyuura/genlayer-redline/5209cd09de90e7e25e3b693d1f4ea5305915ad4e/examples/terms-v2.md),
[v3](https://raw.githubusercontent.com/0xyuura/genlayer-redline/5209cd09de90e7e25e3b693d1f4ea5305915ad4e/examples/terms-v3.md).
`LockedDeposit` watches `refund_window` and `data_export`, with a 30 day lock.

| Step | Result |
| --- | --- |
| baseline of `r1` (the three terms above) | `ACTIVE`, version 1 ([tx](https://explorer-bradbury.genlayer.com/tx/0xee7ff0a449215a7981613000e47e4f070edb3f8eea99185c30abe5c838d747f7)) |
| baseline of `r2` (adds "a free annual security audit") | `REJECTED`, missing `free_audit` ([tx](https://explorer-bradbury.genlayer.com/tx/0x277626bbb7fed73603302868e1511d06392e8f81ba7d77f60decc1eb848e9537)) |
| member deposits 0.001 GEN, accepts `Grandfather` at version 1 | done |
| member withdraws | `[EXPECTED] LOCKED` ([tx](https://explorer-bradbury.genlayer.com/tx/0x34de79a3a2a97ac173401ee236b8c18e07051837ace671c5a995c06e06155acf)) |
| member proposes a version | `[EXPECTED] NOT_OPERATOR` ([tx](https://explorer-bradbury.genlayer.com/tx/0x4a4e8a7dd76356640364926a751ce95a6104720db3b9edcbeab3c7e623a1c7d4)) |
| review v1 to v2 (a rewrite) | version 2, `weakened: ["price_notice"]` ([tx](https://explorer-bradbury.genlayer.com/tx/0xc875174c722c02f942895e5bb5b0b7183ed80b534caa9599d73644cdbca3624c)) |
| member withdraws | still `[EXPECTED] LOCKED`: `price_notice` is not watched ([tx](https://explorer-bradbury.genlayer.com/tx/0x1ab8b605ae72e0603d475580d3b0cb2a7a1b82eee0da22605d4d6ede80d88f2f)) |
| review v2 to v3 (refund window 30 days to 7) | version 3, `weakened: ["refund_window"]` ([tx](https://explorer-bradbury.genlayer.com/tx/0x802e7c7d8a5c8fd9cba15549441f59dca7dea3c54a50946de11ec7197c84ff82)) |
| member withdraws | paid out early, `TERMS_WEAKENED:refund_window` ([tx](https://explorer-bradbury.genlayer.com/tx/0xabfeb2f936691cf4c08409fa655dba7292809bd4c776e564233c71bbc83722cd)) |

`Grandfather.binding(member)` afterwards:

```json
{"accepted": 1, "bound": 1,
 "blocked_by": {"version": 2, "weakened": ["price_notice"]},
 "source": ".../examples/terms-v1.md"}
```

The same amendment history, two answers: the deposit let the member leave once
the refund term it watches was cut; the grandfather clause kept the member on
version 1 from the first weakening.

**v2 was meant to be benign, and consensus disagreed.** Version 1 says the
price notice "is sent by email to the account address"; version 2 says "We
will email you at least 14 days before". The validators unanimously recorded
that as weakening `price_notice`. That is the strict rule doing its job:
operators who want clean amendments should keep protected sentences intact.

The first review returned `LEADER_TIMEOUT` from the CLI and completed later
in a rotation; a resubmitted review was then correctly refused as
`NO_PROPOSAL`. Status 5 is `Accepted` with the appeal window still open.

```bash
genlayer call 0x0c9858299DF2d108C89c2846e11729f24134da53 get_version --args r1 3
genlayer call 0x0c9858299DF2d108C89c2846e11729f24134da53 weakened_after --args r1 1
genlayer call 0xE9A91581Dc32543c5a6e402F1a6436d318142aB0 binding --args 0xfb332ad96268a9974d32f87daa335f553478a67d
```

## Honest limitations

1. A label is the network's reading of two texts. Immutable sources let anyone
   check it, not avoid it.
2. Strict by design: a rewording that drops a detail is `WEAKENED`, as v2
   showed.
3. Protected terms are fixed at registration; a new term is a new charter.
4. Ten thousand characters per version.
5. The operator may amend as often as it likes; consumers can count versions.
6. The demo deposit is tiny and the lock 30 days; real values are the
   deployer's choice.

## Tests

```bash
python -m unittest discover -s tests     # 44 tests, offline, no model, no chain
```

Covers the source rule, the terms parser and every rejection code, the label
rule validators compare, who may propose and cancel, weakening history, prompt
fences, the contract driven end to end with the validator run on every
nondeterministic call, and both consumers. Five mutations (silence as `KEPT`,
open proposals, an off by one in history, a grandfather clause that rolls past
a weakening, and a deposit that ignores its watch list) all change pinned
behaviour.

## Layout

```
contracts/redline.py          the primitive: charters, baselines, reviews, history
contracts/locked_deposit.py   consumer: a lock that opens when watched terms get worse
contracts/grandfather.py      consumer: you stay on the terms you agreed to
examples/                     the fictional terms used on chain, pinned by commit
tests/test_redline.py         the suite
docs/                         INTEGRATING.md, DESIGN.md
```

## Licence

MIT, see [LICENSE](LICENSE).

# Redline design

## Claim

Once a charter is active, no new version of its document can take away a
protected term without that loss being recorded against the version, by
consensus, permanently, in a form a contract can read without a model.

## The problem this exists for

Terms change. Services rewrite their terms of service, protocols amend their
charters, licences get new versions. The people bound by them agreed to one
version and are rarely asked about the next. Reading the new document again
does not help much: the question that matters is not what the new version
says, it is what it no longer promises.

Judging one document is what every earlier primitive of this kind does, and it
is the wrong shape here. "Does version 3 grant a 30 day refund" is answerable,
but it does not tell a contract whether version 3 took something away from
someone who agreed to version 1, and it has to be asked again, with a model,
every time anyone wants to know.

## The move

Three things are fixed when the charter is registered, and none can change:

1. **The protected terms**, one to eight named sentences written from the
   reader's side.
2. **The operator**, the only address that may propose a new version.
3. **The document**, at an immutable URL.

Before anything else, consensus confirms that the document actually states
every protected term (`STATED` or `NOT_STATED` per term). A charter that
protects a promise its own document never makes is `REJECTED`, so a consumer
can never rely on a term that was never granted.

Each later version is then compared with the one it replaces, and validators
agree on one label per protected term: `KEPT` or `WEAKENED`. The version is
stored with the sorted list of terms it weakened. Nothing is overwritten.

## What validators compare

```json
{"data_export": "KEPT", "price_notice": "KEPT", "refund_window": "WEAKENED"}
```

Exactly the charter's term names, each with one label from a closed set of
two, sorted and serialised canonically. Validators refetch both immutable
versions, rerun the same prompt and compare the strings with `==`. A missing
term, an extra term, a third label such as `UNCLEAR`, or a lowercase label is
a model error and stores nothing.

Two labels, not four. `REMOVED`, `NARROWED` and `STRENGTHENED` would be more
descriptive, and every extra label is another boundary for two honest
validators to land on opposite sides of. Consumers need to know one thing:
was something taken away.

## The burden is on the operator

`KEPT` means the new version still grants the term at least as favourably:
same or wider scope, no new condition, no shorter period, no higher cost.
Anything else is `WEAKENED`, including a version that drops the term, narrows
it, or leaves it unclear. Rewording alone is not weakening, but a rewording
that loses a detail is.

The operator writes both versions and chooses when to amend, so ambiguity is
theirs to avoid. The alternative, treating silence or vagueness as `KEPT`,
would let a protection disappear simply by not being mentioned.

## Why history, not a current flag

A charter keeps every version and what each weakened. `weakened_after(id, n)`
returns the union of terms weakened by any version after `n`. A consumer that
recorded the version someone agreed to can therefore ask, at any later time,
what has been taken from that person since, with a view call and no model.

A single "current terms are acceptable" flag would answer a different
question, for nobody in particular. Two members who joined at different
versions have lost different things, and only a history can tell them apart.

## Who may write

| Write | Who | Policy |
| --- | --- | --- |
| `register` | anyone | the sender becomes the charter's operator, fixed forever |
| `confirm_baseline` | anyone | takes the id only; only while the baseline is pending |
| `propose` | the operator | one pending proposal at a time, immutable URL, not the current one |
| `cancel` | the operator | withdraws the pending proposal; records nothing |
| `review` | anyone | takes the id only; compares the stored current and pending URLs |

`review` is open on purpose. It has no input beyond the id, so the caller
cannot choose what is compared or how. Restricting it to the operator would
let the operator leave a bad amendment pending forever while pointing people
at it.

`cancel` does let the operator withdraw a proposal before it is reviewed. That
is safe: a cancelled proposal never becomes the current version, so nothing
has changed for anyone.

## Two consumers, opposite answers

| Consumer | A weakening means |
| --- | --- |
| `LockedDeposit` | exit: if a term it watches was weakened since you deposited, you may withdraw before your lock ends |
| `Grandfather` | consent: you stay bound by the last version before the weakening until you accept again |

`LockedDeposit` pins which terms it watches at deployment. A deposit that only
depends on refunds should not open because the price notice changed.
`Grandfather` watches every term, because it is about what someone agreed to,
not about money.

Neither calls a model. Both read the same record.

## Failure classes

| Class | Example | Result |
| --- | --- | --- |
| Baseline holds | every term stated | `ACTIVE`, version 1 recorded |
| Baseline fails | a term the document never states | `REJECTED`, with the missing terms |
| Benign amendment | reworded, new section | new version, `weakened: []` |
| Adverse amendment | refund window cut from 30 to 7 days | new version, `weakened: ["refund_window"]` |
| Lossy rewording | a detail silently dropped | `WEAKENED` for that term |
| Outsider proposal | anyone but the operator | refused, `NOT_OPERATOR` |
| Mutable source | branch URL, ordinary website | refused, `SOURCE_NOT_IMMUTABLE` |
| Unreachable source | fetch not 200 | `[EXTERNAL]`, nothing stored, review again |
| Model error | missing term, unknown label | `[LLM_ERROR]`, nothing stored |
| Honest disagreement | validators read the change differently | nothing stored, review again |

## Prompt injection

Both versions are written by the operator, who benefits from `KEPT`. They are
fenced with a tag derived from the sha256 of the terms and both documents, and
a document that already contains its tag is refused. Structurally, an
injection can at most move labels within a closed set of two, in a version
that is public and immutable, so anyone can read the text that earned it and
judge the operator accordingly.

## Limits

1. **A label is the network's reading of two texts.** The immutable sources
   let anyone check it, not avoid it.
2. **Strict by design.** A rewording that drops a small detail is `WEAKENED`.
   On chain, version 2 of the example rephrased the price notice as "We will
   email you at least 14 days before", where version 1 also said the notice
   goes to the account address, and it was recorded as weakening
   `price_notice`. The model does not say why; that difference is the only
   one in the clause.
   Operators who want clean amendments should keep protected sentences as
   they were.
3. **Protected terms are fixed.** A charter that needs a new protected term is
   a new charter. Adding one later would let an operator protect something
   only after it was already safe.
4. **Ten thousand characters per version.** Longer documents should protect
   terms from the section that holds them, not the whole agreement.
5. **The operator can amend as often as it likes.** Redline records; it does
   not rate limit. A consumer that cares can count versions.

## Rejected alternatives

- **Judge each version on its own against the terms.** Answers "does it
  state the term", not "did it get worse", and misses a period cut from 30
  days to 7 when both versions technically grant a refund.
- **A continuous similarity score between versions.** Not comparable across
  validators without a tolerance band, and a band is where a small, important
  cut hides.
- **Let the operator declare which terms changed.** The party with the
  incentive to under-report does the reporting.
- **One mutable "current terms" record.** Deletes the history consumers need
  to know what each member has lost.
- **Allow adding protected terms after registration.** See limit 3.

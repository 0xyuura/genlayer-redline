# Integrating Redline

Redline is live on Testnet Bradbury at
`0x0c9858299DF2d108C89c2846e11729f24134da53`.

## 1. Register a charter

```bash
genlayer write 0x0c9858299DF2d108C89c2846e11729f24134da53 register --args \
  "Lanternbox terms of service" \
  '[{"name":"refund_window","text":"Customers may request a full refund within 30 days of purchase."}]' \
  https://raw.githubusercontent.com/<owner>/<repo>/<40 hex sha>/terms.md
```

Returns `r1`. The sender is the operator, for good. Terms: 1 to 8, names in
`snake_case` up to 32 characters, text up to 300 characters.

Refused: `TITLE_TYPE`, `TITLE_LENGTH`, `TERMS_NOT_JSON`, `TERMS_SHAPE`,
`TERM_KEYS`, `TERM_NAME`, `TERM_DUP`, `TERM_TEXT`, `SOURCE_NOT_IMMUTABLE`.
`check_terms` and `check_source` answer the same questions as views.

## 2. Confirm the baseline

```bash
genlayer write 0x0c9858299DF2d108C89c2846e11729f24134da53 confirm_baseline --args r1
```

Anyone may call it. Returns `ACTIVE`, or `REJECTED` with the missing terms in
`get_charter`.

## 3. Amend

The operator proposes; anyone reviews.

```bash
genlayer write <redline> propose --args r1 https://raw.githubusercontent.com/<owner>/<repo>/<new sha>/terms.md
genlayer write <redline> review --args r1
```

`review` returns `{"version": 2, "weakened": [...]}`. `propose` refuses
`NOT_OPERATOR`, `NOT_ACTIVE`, `PROPOSAL_PENDING` and `SAME_SOURCE`. `cancel`
withdraws a pending proposal (operator only). A failed review
(`[EXTERNAL] SOURCE_UNREACHABLE`, `[LLM_ERROR] ...`, or no agreement) stores
nothing; send it again.

## 4. Consume

Record the version a user agreed to, then ask what was taken since:

```python
view = gl.get_contract_at(REDLINE).view()
joined = int(view.latest(CHARTER))                          # when they sign up
lost = json.loads(view.weakened_after(CHARTER, joined))     # any time later
if set(lost) & MY_WATCHED_TERMS:
    ...  # your policy: let them leave, stop binding them, ask again
```

## Views

| View | Returns |
| --- | --- |
| `get_charter(id)` | operator, title, terms, state, current, pending, missing, versions |
| `get_version(id, n)` | `{"n", "source", "weakened", "at"}` |
| `latest(id)` | the newest version number |
| `weakened_after(id, n)` | sorted terms weakened by any version after `n` |
| `check_source(url)`, `check_terms(json)` | validation with no model |
| `counts()` | charters by state |

## Writing terms that review well

- One promise per term, in the words the document uses.
- When amending, leave protected sentences as they are. A rewrite that drops a
  detail is `WEAKENED`.
- Keep versions under 10,000 characters.

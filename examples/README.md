# secret-guard — examples

Each scenario shows: a file containing fake-but-realistic secrets, the exact command, and the redacted report secret-guard produces.

> ⚠ The fixture file `leaked-config.py` is **generated locally**, never committed. Platform-side secret scanners (GitHub Push Protection, GitLab, etc.) flag *any* `sk_live_…` / `xoxb-…` literal — even synthetic ones — so we keep them out of the public repo. Build the fixture on demand:
>
> ```sh
> cd examples && ./make-fixture.sh
> ```
>
> The values produced match every pattern but are deliberately low-entropy placeholders that unlock nothing.

---

## Scenario 1 — scan a file directly

**Command:**

```sh
python3 scripts/guard.py --files examples/leaked-config.py --format md
```

**Helper output (verbatim, with full paths trimmed for readability):**

```
# secret-guard report

| File | Line | Pattern | Snippet |
| --- | ---: | --- | --- |
| examples/leaked-config.py | 2 | AWS Access Key       | AWS Access Key: AKIA… |
| examples/leaked-config.py | 3 | Slack token          | Slack token: xoxb… |
| examples/leaked-config.py | 4 | Stripe               | Stripe: sk_l… |
| examples/leaked-config.py | 5 | GitHub PAT           | GitHub PAT: ghp_… |
| examples/leaked-config.py | 6 | Generic high-entropy | Generic high-entropy: MIIE… |
```

**Exit code:** `1` (findings present).

**Notice what's in the report — and what isn't.**

The full secret value never appears. Each snippet is `pattern-name: first-4-chars…`. That's the entire redaction contract, and it's tested by `tests/test_guard.py::test_redaction_contains_only_rule_and_first_four`.

---

## Scenario 2 — scan the staged diff (default mode)

The normal flow for a developer about to commit:

```sh
git add src/config.py
python3 scripts/guard.py --format md
```

The helper reads `git diff --cached` and scans only the *added* lines. Unchanged lines in the file aren't re-flagged.

---

## Scenario 3 — pre-commit hook

To block the commit before it lands:

```sh
cp hooks/pre-commit .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

From now on:

```
$ git commit -m "feat: wire up payments"
🚨 secret-guard found 1 potential secret(s) in staged diff:

| src/config.py | 12 | Stripe | sk_l… |

Commit blocked. To bypass (rotate the key first!), run with --no-verify.
```

---

## Scenario 4 — allowlist for false positives

The generic high-entropy detector occasionally flags long base64 strings that aren't secrets (e.g. cache keys, minified bundles). Allowlist them:

```sh
echo '^[a-f0-9]{64}$' > .secret-allowlist        # SHA-256 hashes
echo '^src/test/fixtures/' >> .secret-allowlist   # test fixtures
python3 scripts/guard.py --allowlist .secret-allowlist --format md
```

Each line in the allowlist is a Python regex. A finding is suppressed if the **snippet OR the file path** matches any allowlist line.

---

## Pattern reference

| Rule | Matches | Example (fake) |
|---|---|---|
| AWS Access Key | `AKIA[0-9A-Z]{16}` | `AKIAAAAAAAAAAAAAAAAA` |
| GitHub PAT | `gh[pousr]_[A-Za-z0-9]{36,}` | `ghp_…36+chars…` |
| Slack token | `xox[abpr]-[A-Za-z0-9-]{10,}` | `xoxb-1234567890-…` |
| Stripe | `sk_(live|test)_[A-Za-z0-9]{24,}` | `sk_live_FAKE…` |
| Google API key | `AIza[0-9A-Za-z_-]{35}` | `AIza…35chars` |
| JWT | `eyJ…\.eyJ…\..*` | `eyJ…` |
| Private key | `-----BEGIN … PRIVATE KEY-----` | (literal header) |
| Generic high-entropy | base64-ish ≥32 chars, Shannon entropy ≥4.5 | (catches the unknown unknowns) |

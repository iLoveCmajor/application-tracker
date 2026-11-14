# Process

How work moves from an issue to `main`. The tracker is the repo's
[GitHub Issues](https://github.com/iLoveCmajor/application-tracker/issues); every task lives there.

## Roles

| Role | Follows | Input | Output | Must not |
| --- | --- | --- | --- | --- |
| Orchestrator | this file | the backlog | runs the roles below in order, merges, closes issues on PASS | write product code itself |
| PM | [`team/pm.md`](team/pm.md) | a raw issue | the issue body rewritten from [`task-template.md`](task-template.md), follow-up issues for anything cut | write code |
| Software Engineer | [`team/software-engineer.md`](team/software-engineer.md) | a groomed issue, plus the QA comment on a retry | code, tests, a commit (or a pull request), a comment on the issue | change the criteria, close the issue |
| QA Engineer | [`team/qa-engineer.md`](team/qa-engineer.md) | the criteria and the running code | a `## QA: PASS` or `## QA: FAIL` comment with evidence per criterion | fix code, trust the engineer's comment |

The orchestrator is the main agent session. Each role runs as a **separate subagent with a fresh
context**, so QA never grades work it wrote.

## Lifecycle of an issue

```text
raw issue ──PM──▶ groomed (label: groomed)
          ──Engineer──▶ implemented (comment: "## Engineer: done")
          ──QA──▶ PASS ──orchestrator──▶ merged, issue closed
                  FAIL ──▶ back to a fresh Engineer with the QA comment as input
```

1. **Groom.** The PM rewrites the issue body into the template, adds the `groomed` label and comments
   `## PM: groomed`.
2. **Implement.** The engineer works on the issue's branch (`issue-<n>-<slug>`) once CI exists,
   or on `main` before that, with commits that reference the issue (`#<n>`). It comments
   `## Engineer: done` with what changed, the commands it ran and their results.
3. **Test.** QA runs the tests and checks every criterion against the running code (requests against
   the API, the page in a browser, the container). It comments `## QA: PASS` or `## QA: FAIL`, one line
   of evidence per criterion. One failed criterion makes the verdict FAIL.
4. **Close.** On PASS, the orchestrator merges the pull request (CI must be green) and closes the issue.
   On FAIL, a new engineer gets the issue and the QA comment. After three FAILs the orchestrator
   stops and asks the human.

Every comment starts with the role that wrote it, so the history on each issue reads as a hand-off.

## Branches and pull requests

- Before CI exists (issues #1–#9), work lands on `main` in commits that reference the issue.
- From issue #10 on: one branch and one pull request per issue. The pull request says `Closes #<n>`.
  CI runs the tests on it; nothing merges red.
- Commit messages are short and plain.

## What the human does

Vladimir writes the plan and the spec, reads the diffs at each merge, owns the deployment account and
its secrets, and clicks through the deployed app. Agents never touch credentials.

## Definition of done for the backlog

- Every issue closed with a `## QA: PASS` comment.
- `make test` green from a fresh clone; `docker compose up` serves the app.
- The README's links all open, including the public URL.

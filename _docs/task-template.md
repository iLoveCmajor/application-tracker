# Task template

Every issue is groomed into this shape by the PM before anyone writes code.

```markdown
## Goal
<one or two sentences: what is true when this is done>

## Acceptance criteria
- [ ] AC-<issue>.1 <a yes/no statement someone can check against running code>
- [ ] AC-<issue>.2 <include the edge cases: empty, too long, missing, wrong id>

## Out of scope
- <what this issue does not do> → #<follow-up issue>

## Constraints
- <files, libraries and earlier decisions to respect; links to _docs/specs.md sections>
```

Rules for the criteria:

- Each one is checkable by running something: a request, a test, a command, a page in the browser.
- Each one has an id (`AC-3.2` is issue #3, criterion 2). Tests reference the id in their name or
  docstring.
- Anything moved out of scope goes to a linked issue. Nothing is dropped silently.

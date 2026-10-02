---
description: Convert a notes file into two — split into Part 1/Part 2, a two-column table, or a notes + revision sheet.
---

# Convert Notes Into Two

Take the notes file at `$1` and convert it into two artefacts.

**Mode:** `$2` — one of:

| Mode | Result |
|---|---|
| `split` *(default)* | Two files: `<name>.part1.md` and `<name>.part2.md` |
| `columns` | One file re-laid out as two-column comparison tables |
| `sheet` | `<name>.md` (kept) + `<name>.revision.md` — a one-page exam sheet |

If `$2` is empty, use `split`.

## Shared rules

- **Read `$1` completely first.** Never convert a file you have not read in full.
- **Preserve every fact.** Splitting must lose nothing — a rule that exists in the source must exist in the output.
- Keep the existing heading depth, table formatting and `backticks` style. Match the source file's voice.
- Do not rewrite the prose into your own words. Reorganise, don't rewrite.
- Write files with the `write` tool. Do not shell out to `echo`/`Out-File`.

---

## Mode `split`

Find the natural break in the document — the point where the topic turns over. Split *there*, not in the middle of a section.

- If the file has a `## 1. What is this?` and a `## 2. The main rules` shape, Part 1 is "What is this?" and Part 2 is everything from "The main rules" onward.
- Balance the two halves so neither is trivially short.

`<name>.part1.md`:

```markdown
# <Topic> — Part 1 of 2: <break section name>

<sections>

---
*Part 2: [part2](<name>.part2.md)*
```

`<name>.part2.md`:

```markdown
# <Topic> — Part 2 of 2: <break section name>

<sections>

---
*Part 1: [part1](<name>.part1.md)*
```

Carry the `**Source:**` line into Part 1. Part 2 gets a `*Continued from Part 1.*` line.

## Mode `columns`

Rewrite the same content in place as `<name>.columns.md`, converting every mapping table into a two-column layout and every direct/indirect pair into a direct | indirect pair:

```markdown
# <Topic> — Comparison View

## <Section>

| Direct | Reported |
|---|---|
| `will` | `would` |
| today | that day |

## <Section>

| Rule | Result |
|---|---|
| Positive command | `to + verb` |
```

Omit the "in place" part — write a **new** file, never modify `$1`.

## Mode `sheet`

Leave `$1` untouched. Write `<name>.revision.md`:

```markdown
# <Topic> — Revision Sheet

## The rules
Numbered, one line each, with the trigger keyword in bold.

## Word changes
| Direct | Reported |
|---|---|

## Trap words
The commonly confused pairs, as a table.

## 3 things to remember
The three highest-yield takeaways.

---
*Full notes: [<name>](<name>) · Source: <URL>*
```

Keep it under one page. It is a recall aid, not a summary — every line must be something you would be tested on.

---

After converting, reply with the files written, the byte size of each, and one line per part naming what it covers.

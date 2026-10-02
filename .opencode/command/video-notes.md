---
description: Pull a YouTube video's transcript and turn it into structured study notes saved under notes/.
---

# Video Notes

Turn the YouTube video at `$ARGUMENTS` into clean, structured study notes.

## 1. Fetch the transcript

```bash
python -m pip install -U yt-dlp yt-dlp-ejs
python -m yt_dlp --js-runtimes node --skip-download --write-auto-subs --sub-langs "en" --sub-format vtt -o "$TMP/%(id)s" "<URL>"
```

- `--js-runtimes node` is required — without it YouTube returns PO-token errors and no subtitles.
- If the node runtime is missing, retry with `--js-runtimes deno`.
- Retry once after ~60s if you get `HTTP Error 429`.

If `yt-dlp` is missing entirely, ask the user before installing anything into their project venv.

## 2. Flatten the VTT to plain text

Auto-captions arrive as rolling, overlapping fragments. Strip timestamps, `WEBVTT` headers, and inline tags, then collapse consecutive duplicates. Write the result to a `.txt` next to the `.vtt`.

Read the flattened transcript **in full** before writing anything. Do not skim or guess — the notes must come from what the speaker actually said.

## 3. Write the notes

Save to `notes/<slug>.md`, where the slug is a short lowercase-hyphenated title.

Structure:

```markdown
# <Topic> — <Class / Subject> <Level>

**Source:** [<Video title>](<URL>)
**Channel:** <name> · **Length:** <mm:ss> · **Published:** <date>

## 1. What is this?
Short definition, plus a direct-vs-contrasting table where one is natural.

## 2. The main rules
One `##`/`###` per rule. Use a table whenever there is a mapping
(direct → indirect, old word → new word, positive → negative).

## 3. Common confusions
The bit the teacher spent most time warning about.

## 4. Solved practice set
| # | Given | Answer |
|---|---|---|

## 5. Cheat sheet
Numbered, exam-ready revision list.
```

Rules for the notes:

- **Correct the transcript, don't copy it.** Auto-captions garble grammar terms — write the real English, not what the recogniser heard.
- **Preserve the teacher's own examples and order of explanation.**
- **Never invent content** that is not in the transcript. If the video skips something, leave it out.
- Tables for mappings, code-style `backticks` for the actual phrases (`not to forget`), bold for the takeaway in each rule.
- Add a line at the end: `Source: <URL> (auto-captions, lightly corrected)`.

After writing, reply with the file path and a 3-bullet summary of what the video covered.

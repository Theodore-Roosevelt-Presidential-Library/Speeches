# Transcriptions

New transcriptions made by the Theodore Roosevelt Presidential Library from the typescripts in the
Theodore Roosevelt Papers at the Library of Congress (Series 5). One file per speech, named by speech id.

Files are **diplomatic**: they keep what is on the page, including typing errors, overstrikes and hand
corrections. `scripts/transcripts.py` turns each file into two views: the diplomatic view, and a
reading view that applies the corrections. Both views are published; the reading view is shown first.

## Header

```
---
speech: 1903-04-07-medora
source: Library of Congress, Theodore Roosevelt Papers, Series 5, reel 425, frame 274
image: https://tile.loc.gov/image-services/iiif/service:mss:mss38299:mss38299_425:0274
transcribed: 2026-10-27 (pass 1)
checked: 2026-10-27 (pass 2, independent read)
---
```

## Markup

| Mark | Means | Diplomatic view | Reading view |
|---|---|---|---|
| `[pb 97 425:0274]` | New page; folio number written on the page, then reel:frame | page marker | hidden |
| `[-text-]` | Struck through (by hand, or x-ed out on the typewriter) | struck through | left out |
| `[+text+]` | Added by hand | shown as an insertion | kept |
| `{typed\|reading}` | Typing slip and the obvious intended reading | typed | reading |
| `[?text?]` | Uncertain reading | marked uncertain | kept, marked uncertain |
| `[illegible]` | Cannot be read | shown | shown |
| `[margin: text]` | Handwriting in the margin, not part of the speech | shown as a note | hidden |
| `[note: text]` | Transcriber's note | shown as a note | hidden |

Paragraphs are separated by a blank line, as on the page. Line breaks within a paragraph are not kept.
Everything else (spelling, punctuation, "(Applause)") is as typed.

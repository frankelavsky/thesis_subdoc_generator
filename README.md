# Thesis variant builder

Build custom subset PDFs of thesis (specific chapters, specific sections,
any combination of frontmatter blocks) from a single `main.tex`, without
restructuring source.

## What it does

Drop `build_variants.py` and `variants.conf` into thesis project directory
(alongside `main.tex`). Define named variants in `variants.conf`:

```
full                = all
committee_preview   = title, keywords, abstract, acknowledgements, toc, 1, 2, 9.1, 9.3, references
personal_copy       = acknowledgements, 1.1, 9.1, bio
```

Run the script. You get one PDF per variant in `variants/`.

**Part identifiers:** `title`, `keywords`, `abstract`, `acknowledgements` (or
`acknowledgments`), `toc`, `bio`, `references`, `discussion`, `all`, plus
chapter numbers (`1`, `2`, …) and section refs (`9.1`, `9.3`, …). Asking for
just `9.1` gives you the chapter's intro text plus section 9.1 only.

Chapter/section/part numbers are preserved correctly — if you exclude chapter
3, chapter 9 still appears as Chapter 9 (not 3). If you include section 9.3 but
not 9.2, it still shows as "9.3".

## Abridged-variant cover page

Every variant *except* the full one automatically gets a cover page inserted as
its first page. It contains:

1. A centered notice with the archival URL.
2. A "This document contains the following sections:" list, reflecting exactly
   what was requested (frontmatter items, full chapters, or partial chapters
   noted like "Chapter 9: Discussion & Future Work (Sections 9.1 and 9.3 only)").
3. A "This document does not contain the following chapters:" list, showing
   which chapters are absent.

**The rule:** a variant is "full" iff its parts list contains the literal token
`all`. Any other variant is treated as abridged and gets the cover page.

To change the archival URL, either edit the `DEFAULT_ARCHIVE_URL` constant at
the top of `build_variants.py`, or pass `--archive-url` on the command line.

To override the auto-detection:
- `--no-cover` — never add a cover page, even for abridged variants
- `--force-cover` — add a cover page even to the full variant

## Setup

Requires **Python 3** and a **LaTeX distribution**:
- macOS: `brew install --cask mactex` (full) or `basictex` (smaller, + install
  missing packages with `tlmgr` as errors appear)
- Ubuntu/Debian: `sudo apt install texlive-full`
- Windows: install [MiKTeX](https://miktex.org/) (auto-installs missing packages)

Check it's working: `latexmk --version` should print something.

## Usage

Build every variant in `variants.conf`:
```
python3 build_variants.py
```

Emit the sliced `.tex` files only (skip PDF compilation, useful for debugging):
```
python3 build_variants.py --no-compile
```

One-off from the command line without touching the config:
```
python3 build_variants.py --name quickdraft \
    --parts "title,abstract,1,9.1,bio"
```

Show LaTeX's output during compilation (useful when something fails):
```
python3 build_variants.py --verbose
```

Full options: `python3 build_variants.py --help`.

## Output layout

```
variants/
├── committee_preview.pdf       ← top-level: easy-access copies
├── personal_copy.pdf
├── full.pdf
├── committee_preview/          ← per-variant working dirs
│   ├── committee_preview.tex
│   ├── committee_preview.pdf
│   ├── committee_preview.aux / .log / .toc ...
│   ├── cmuthesis.cls           ← symlinks back to your real files
│   ├── biblio.bib
│   ├── figs/
│   └── ...
└── personal_copy/
    └── ...
```

The per-variant directories contain symlinks to your real class files,
bibliography, and figure folders — so the script doesn't duplicate your assets.
On Windows the symlinks are replaced with copies automatically.

## Known caveats

1. **Cross-references to excluded content render as `?`.** If a variant
   includes text with `\cite{...}` or `\ref{...}` pointing into an excluded
   chapter, those show up as `?`. This is LaTeX's standard behavior, not a
   script bug. If you want clean references, include `references` in the
   parts list for that variant — the script still only compiles bib entries
   that are actually cited in the included content.
2. **Figure numbering shifts inside partially-included chapters.** The script
   forces chapter, section, and part counters, but not figure counters. If you
   include section 9.1 and 9.3 of a chapter where figures were interleaved,
   figure numbers inside 9.3 may shift down by however many figures were in
   9.2. Usually fine for review copies.
3. **Overleaf doesn't run this.** Overleaf's compile servers don't execute
   arbitrary Python during the build. This is a pre-processing step you run
   locally (or in CI). Your Overleaf project itself is unchanged — keep writing
   normally; the script just slices the source when you want variants.

## Optional: auto-build on Overleaf push via GitHub Actions

If you're on Overleaf Premium and have the GitHub integration set up, you can
have variants rebuild automatically whenever you sync from Overleaf to GitHub.
Add `.github/workflows/build-variants.yml`:

```yaml
name: Build thesis variants
on: [push, workflow_dispatch]
jobs:
  build:
    runs-on: ubuntu-latest
    container: texlive/texlive:latest
    steps:
      - uses: actions/checkout@v4
      - name: Build variants
        run: python3 build_variants.py
      - name: Upload PDFs
        uses: actions/upload-artifact@v4
        with:
          name: thesis-variants
          path: variants/*.pdf
```

Variants then appear as downloadable artifacts on each commit.

#!/usr/bin/env python3
"""
build_variants.py — Build customized PDF variants of a single-file LaTeX thesis.

Reads a variants config and produces one .tex (and, optionally, one PDF) per
variant by slicing the original main.tex along chapter / section / frontmatter
boundaries.

Part identifiers accepted:
    title                   → \\title{...} ... \\maketitle
    keywords                → \\begin{keywords} ... \\end{keywords}
    abstract                → \\chapter*{Abstract}
    acknowledgements        → \\chapter*{Acknowledgments}  (also "acknowledgments")
    toc                     → \\tableofcontents (+ \\listoffigures)
    N                       → entire chapter N (e.g. "1", "9")
    N.M                     → intro of chapter N + section M only (e.g. "9.1")
                              multiple N.M for the same N are combined
    bio                     → the Biographical Sketch chapter
    discussion              → the "Discussion & Future Work" chapter (alias)
    references              → the bibliography

Usage:
    # Build every variant defined in variants.conf and compile to PDF:
    python build_variants.py

    # Build without compiling (just emit the variant .tex files):
    python build_variants.py --no-compile

    # One-off from the command line (no config file needed):
    python build_variants.py --name committee \\
        --parts "title,keywords,abstract,acknowledgements,toc,1,2,9.1,9.3"
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path


# --- Parsing ----------------------------------------------------------------

CHAPTER_STAR_RE = re.compile(r'\\chapter\s*\*\s*\{(.+?)\}\s*$')
CHAPTER_RE      = re.compile(r'\\chapter\s*\{(.+?)\}\s*$')
SECTION_RE      = re.compile(r'\\section\s*\*?\s*\{(.+?)\}\s*$')
PART_RE         = re.compile(r'\\part\s*\{(.+?)\}\s*$')

# LaTeX allows whitespace between control sequences and their braces.
BEGIN_DOC_RE    = re.compile(r'\\begin\s*\{document\}')
END_DOC_RE      = re.compile(r'\\end\s*\{document\}')
BEGIN_KW_RE     = re.compile(r'\\begin\s*\{keywords\}')
END_KW_RE       = re.compile(r'\\end\s*\{keywords\}')
MAKETITLE_RE    = re.compile(r'\\maketitle\b')
FRONTMATTER_RE  = re.compile(r'\\frontmatter\b')
MAINMATTER_RE   = re.compile(r'\\mainmatter\b')
BACKMATTER_RE   = re.compile(r'\\backmatter\b')
TITLE_CMD_RE    = re.compile(r'\\title\s*\{')
PAGESTYLE_PL_RE = re.compile(r'\\pagestyle\s*\{plain\}')
TOC_RE          = re.compile(r'\\tableofcontents\b')
LOF_RE          = re.compile(r'\\listoffigures\b')
LOT_RE          = re.compile(r'\\listoftables\b')
BIBSECTION_RE   = re.compile(r'\\renewcommand\s*\{\s*\\bibsection\s*\}')
BIBSTYLE_RE     = re.compile(r'\\bibliographystyle\s*\{')
BIBLIO_RE       = re.compile(r'\\bibliography\s*\{')


class Thesis:
    """Structural map of main.tex. Stores line numbers of every landmark."""

    def __init__(self, lines):
        self.lines = lines
        self.begin_document = None
        self.end_document = None
        self.frontmatter = None
        self.mainmatter = None
        self.backmatter = None
        self.maketitle = None
        self.title_start = None
        self.keywords_begin = None
        self.keywords_end = None
        self.pagestyle_plain = None
        self.toc_start = None
        self.toc_end = None
        self.abstract_start = None
        self.acknowledgments_start = None
        self.parts = []      # [{line, title, number, chapters: [ch_idx, ...]}, ...]
        self.chapters = []   # [{line, title, number, sections, part_idx}, ...]
        self.bio_chapter_idx = None
        self.bibliography_start = None
        self._parse()

    def _parse(self):
        current_chapter_idx = None
        current_part_idx = None
        main_chapter_counter = 0
        bib_setup_start = None

        for i, raw_line in enumerate(self.lines):
            line = raw_line.lstrip()
            if BEGIN_DOC_RE.match(line):
                self.begin_document = i
            elif END_DOC_RE.match(line):
                self.end_document = i
            elif FRONTMATTER_RE.match(line):
                self.frontmatter = i
            elif MAINMATTER_RE.match(line):
                self.mainmatter = i
            elif BACKMATTER_RE.match(line):
                self.backmatter = i
            elif MAKETITLE_RE.match(line):
                self.maketitle = i
            elif TITLE_CMD_RE.match(line) and self.title_start is None:
                self.title_start = i
            elif BEGIN_KW_RE.match(line):
                self.keywords_begin = i
            elif END_KW_RE.match(line):
                self.keywords_end = i
            elif PAGESTYLE_PL_RE.match(line) and self.pagestyle_plain is None:
                self.pagestyle_plain = i
            elif TOC_RE.match(line):
                if self.toc_start is None:
                    self.toc_start = i
                self.toc_end = i
            elif LOF_RE.match(line) or LOT_RE.match(line):
                if self.toc_start is not None:
                    self.toc_end = i
            elif PART_RE.match(line):
                m = PART_RE.match(line)
                self.parts.append({
                    'line': i,
                    'title': m.group(1),
                    'number': len(self.parts) + 1,
                    'chapters': [],
                })
                current_part_idx = len(self.parts) - 1
            elif CHAPTER_STAR_RE.match(line):
                title = CHAPTER_STAR_RE.match(line).group(1)
                low = title.lower()
                if low == 'abstract':
                    self.abstract_start = i
                elif low in ('acknowledgments', 'acknowledgements'):
                    self.acknowledgments_start = i
            elif CHAPTER_RE.match(line):
                title = CHAPTER_RE.match(line).group(1)
                main_chapter_counter += 1
                chapter_idx = len(self.chapters)
                self.chapters.append({
                    'line': i,
                    'title': title,
                    'number': main_chapter_counter,
                    'sections': [],
                    'part_idx': current_part_idx,
                })
                if current_part_idx is not None:
                    self.parts[current_part_idx]['chapters'].append(chapter_idx)
                current_chapter_idx = chapter_idx
                if 'biograph' in title.lower():
                    self.bio_chapter_idx = chapter_idx
            elif SECTION_RE.match(line) and current_chapter_idx is not None:
                stitle = SECTION_RE.match(line).group(1)
                ch = self.chapters[current_chapter_idx]
                ch['sections'].append({
                    'line': i,
                    'title': stitle,
                    'number': len(ch['sections']) + 1,
                })
            elif BIBSECTION_RE.match(line):
                if bib_setup_start is None:
                    bib_setup_start = i
            elif BIBSTYLE_RE.match(line) or BIBLIO_RE.match(line):
                if bib_setup_start is None:
                    bib_setup_start = i
                self.bibliography_start = bib_setup_start

        if self.bibliography_start is None and bib_setup_start is not None:
            self.bibliography_start = bib_setup_start

    # ---- span helpers ------------------------------------------------------

    def chapter_range(self, ch_idx):
        """Half-open line range [start, end) for the full chapter."""
        start = self.chapters[ch_idx]['line']
        ends = [self.end_document if self.end_document is not None else len(self.lines)]
        if ch_idx + 1 < len(self.chapters):
            ends.append(self.chapters[ch_idx + 1]['line'])
        for p in self.parts:
            if p['line'] > start:
                ends.append(p['line'])
        if self.backmatter is not None and self.backmatter > start:
            ends.append(self.backmatter)
        if self.bibliography_start is not None and self.bibliography_start > start:
            ends.append(self.bibliography_start)
        return start, min(ends)

    def chapter_intro_range(self, ch_idx):
        """From \\chapter{...} up to (but not including) its first \\section{...}."""
        start, end = self.chapter_range(ch_idx)
        secs = self.chapters[ch_idx]['sections']
        if secs:
            end = secs[0]['line']
        return start, end

    def section_range(self, ch_idx, sec_idx):
        """From \\section{...} up to next \\section or end-of-chapter."""
        secs = self.chapters[ch_idx]['sections']
        s_start = secs[sec_idx]['line']
        _, ch_end = self.chapter_range(ch_idx)
        if sec_idx + 1 < len(secs):
            return s_start, secs[sec_idx + 1]['line']
        return s_start, ch_end


# --- Variant resolution -----------------------------------------------------

def normalize_part(p):
    p = p.strip().lower()
    aliases = {
        'acknowledgments': 'acknowledgements',
        'tableofcontents': 'toc',
        'contents': 'toc',
    }
    return aliases.get(p, p)


def resolve_wanted(parts_spec, thesis):
    wanted = {
        'title': False,
        'keywords': False,
        'toc': False,
        'abstract': False,
        'acknowledgements': False,
        'main_chapters': {},   # ch_idx -> 'all' or set of section numbers
        'bio': False,
        'references': False,
    }
    bio_idx = thesis.bio_chapter_idx
    discussion_idx = None
    for idx, ch in enumerate(thesis.chapters):
        if idx == bio_idx:
            continue
        if 'discussion' in ch['title'].lower():
            discussion_idx = idx
            break

    for raw in parts_spec:
        p = normalize_part(raw)
        if p == 'all':
            wanted.update({'title': True, 'keywords': True, 'toc': True,
                           'abstract': True, 'acknowledgements': True,
                           'bio': True, 'references': True})
            for idx in range(len(thesis.chapters)):
                if idx != bio_idx:
                    wanted['main_chapters'][idx] = 'all'
        elif p in ('title', 'keywords', 'toc', 'abstract',
                   'acknowledgements', 'bio', 'references'):
            wanted[p] = True
        elif p == 'discussion':
            if discussion_idx is None:
                raise ValueError("Could not locate a 'Discussion' chapter")
            wanted['main_chapters'].setdefault(discussion_idx, 'all')
        elif re.fullmatch(r'\d+', p):
            num = int(p)
            idx = next((i for i, ch in enumerate(thesis.chapters)
                        if ch['number'] == num), None)
            if idx is None:
                raise ValueError(f"Chapter {num} not found")
            if idx == bio_idx:
                wanted['bio'] = True
            else:
                wanted['main_chapters'][idx] = 'all'
        elif re.fullmatch(r'\d+\.\d+', p):
            ch_num, sec_num = (int(x) for x in p.split('.'))
            idx = next((i for i, ch in enumerate(thesis.chapters)
                        if ch['number'] == ch_num), None)
            if idx is None:
                raise ValueError(f"Chapter {ch_num} not found")
            if idx == bio_idx:
                raise ValueError("Bio has no numbered sections")
            existing = wanted['main_chapters'].get(idx)
            if existing != 'all':
                existing = set(existing) if existing else set()
                existing.add(sec_num)
                wanted['main_chapters'][idx] = existing
        else:
            raise ValueError(f"Unknown part identifier: {raw!r}")
    return wanted


# --- Assembly ---------------------------------------------------------------

# Archive URL shown on cover pages of abridged variants. Edit this, or override
# per-run with --archive-url.
DEFAULT_ARCHIVE_URL = "http://reports-archive.adm.cs.cmu.edu/anon/hcii/CMU-HCII-26-103.pdf"


def _format_section_list(sec_labels):
    """Render ['9.1', '9.3'] as 'Sections 9.1 and 9.3 only', handling 1/2/N+."""
    if len(sec_labels) == 1:
        return f"Section {sec_labels[0]} only"
    if len(sec_labels) == 2:
        return f"Sections {sec_labels[0]} and {sec_labels[1]} only"
    return f"Sections {', '.join(sec_labels[:-1])}, and {sec_labels[-1]} only"


def build_cover_lists(wanted, thesis):
    """Return (included, excluded_chapters) — two lists of LaTeX-safe label strings."""
    included = []
    excluded_chapters = []

    # Frontmatter bits, in the order they appear in the document
    if wanted['title']:
        included.append("Title page")
    if wanted['keywords']:
        included.append("Keywords")
    if wanted['abstract']:
        included.append("Abstract")
    if wanted['acknowledgements']:
        included.append("Acknowledgements")
    if wanted['toc']:
        included.append("Table of contents")

    # Main chapters (numbered), in file order, excluding bio
    for idx, ch in enumerate(thesis.chapters):
        if idx == thesis.bio_chapter_idx:
            continue
        label = f"Chapter {ch['number']}: {ch['title']}"
        if idx in wanted['main_chapters']:
            spec = wanted['main_chapters'][idx]
            if spec == 'all':
                included.append(label)
            else:
                sec_labels = [f"{ch['number']}.{n}" for n in sorted(spec)]
                included.append(f"{label} ({_format_section_list(sec_labels)})")
        else:
            excluded_chapters.append(label)

    # Bio (unnumbered in structure but still a "chapter" in the TOC)
    if thesis.bio_chapter_idx is not None:
        bio = thesis.chapters[thesis.bio_chapter_idx]
        bio_label = f"Chapter {bio['number']}: {bio['title']}"
        if wanted['bio']:
            included.append(bio_label)
        else:
            excluded_chapters.append(bio_label)

    if wanted['references']:
        included.append("References")

    return included, excluded_chapters


def build_cover_page_tex(wanted, thesis, archive_url):
    """Return the LaTeX source for the cover page (one full page, unnumbered)."""
    included, excluded = build_cover_lists(wanted, thesis)

    def render_items(items):
        # enumitem is already loaded in the preamble. We use tight lists.
        inner = "\n".join(f"    \\item {x}" for x in items) if items else \
                "    \\item (none)"
        return ("\\begin{itemize}[leftmargin=2em,itemsep=0.15em,topsep=0.25em]\n"
                f"{inner}\n"
                "\\end{itemize}")

    # Escape underscores in the URL for LaTeX (inside \url{} they're fine, but
    # we use \url so they're safe as-is). The URL goes verbatim.
    return (
        "% ---- Auto-generated cover page (abridged variant) ----\n"
        "\\thispagestyle{empty}\n"
        "\\begingroup\n"
        "\\parindent=0pt\n"
        "\\null\\vfill\n"
        "\\begin{center}\n"
        "{\\large This is an excerpt from Frank Elavsky's dissertation on \\textit{Tool-making as an Intervention on the Accessibility of Interactive Data Experiences}, which can be accessed in full at this archival link:}\\\\[0.8em]\n"
        f"\\url{{{archive_url}}}\n"
        "\\end{center}\n"
        "\\vspace{3em}\n"
        "\\noindent\\textbf{This document contains the following sections:}\n"
        f"{render_items(included)}\n"
        "\\vspace{1em}\n"
        "\\noindent\\textbf{This document does not contain the following chapters:}\n"
        f"{render_items(excluded)}\n"
        "\\vfill\n"
        "\\endgroup\n"
        "\\clearpage\n"
        "% ---- End cover page ----\n"
    )


def is_full_variant(parts_spec):
    """A variant is 'full' (no cover page) iff it contains the literal token 'all'."""
    return any(normalize_part(p) == 'all' for p in parts_spec)


def assemble_tex(thesis, wanted, cover_page_tex=None):
    L = thesis.lines
    out = []

    # 1. Preamble + \begin{document}
    out.extend(L[:thesis.begin_document + 1])

    # 1b. Cover page for abridged variants (injected immediately after \begin{document},
    #     before \frontmatter so it's unnumbered and doesn't interact with page styles).
    if cover_page_tex:
        out.append(cover_page_tex)

    has_frontmatter = any([wanted['title'], wanted['keywords'], wanted['toc'],
                           wanted['abstract'], wanted['acknowledgements']])
    has_mainmatter = bool(wanted['main_chapters']) or wanted['bio']

    # 2. \frontmatter + \pagestyle{empty}
    if thesis.frontmatter is not None:
        front_end = (thesis.title_start
                     if thesis.title_start is not None
                     else thesis.frontmatter + 1)
        out.extend(L[thesis.frontmatter:front_end])

    # 3. Title
    if wanted['title']:
        out.extend(L[thesis.title_start:thesis.maketitle + 1])

    # 4. Keywords
    if wanted['keywords']:
        out.extend(L[thesis.keywords_begin:thesis.keywords_end + 1])

    # 5. \pagestyle{plain} + \clearpage setup before any visible frontmatter
    if has_frontmatter and thesis.pagestyle_plain is not None:
        ps_end = thesis.toc_start if thesis.toc_start is not None else thesis.abstract_start
        if ps_end is None:
            ps_end = thesis.pagestyle_plain + 1
        out.extend(L[thesis.pagestyle_plain:ps_end])

    # 6. TOC
    if wanted['toc']:
        out.extend(L[thesis.toc_start:thesis.toc_end + 1])

    # 7. Abstract
    if wanted['abstract']:
        end = thesis.acknowledgments_start or thesis.mainmatter
        out.extend(L[thesis.abstract_start:end])

    # 8. Acknowledgements
    if wanted['acknowledgements']:
        end = thesis.mainmatter if thesis.mainmatter is not None else thesis.end_document
        out.extend(L[thesis.acknowledgments_start:end])

    # 9. \mainmatter
    if has_mainmatter and thesis.mainmatter is not None:
        first_struct = None
        if thesis.parts:
            first_struct = thesis.parts[0]['line']
        elif thesis.chapters:
            first_struct = thesis.chapters[0]['line']
        if first_struct is not None:
            out.extend(L[thesis.mainmatter:first_struct])
        else:
            out.append(L[thesis.mainmatter])

    # 10. Parts + chapters in file order
    events = []
    for p in thesis.parts:
        events.append((p['line'], 'part', p))
    for i, ch in enumerate(thesis.chapters):
        events.append((ch['line'], 'chapter', i))
    events.sort(key=lambda e: e[0])

    wanted_ch_indices = set(wanted['main_chapters'].keys())
    if wanted['bio'] and thesis.bio_chapter_idx is not None:
        wanted_ch_indices.add(thesis.bio_chapter_idx)

    for k, (ev_line, kind, obj) in enumerate(events):
        if kind == 'part':
            # A part is emitted only if at least one non-bio chapter in it is wanted.
            ch_indices_in_part = [i for i in obj['chapters']
                                  if i != thesis.bio_chapter_idx]
            if not any(i in wanted_ch_indices for i in ch_indices_in_part):
                continue
            # Force correct part number (Roman numerals)
            out.append(f"\\setcounter{{part}}{{{obj['number'] - 1}}}\n")
            # Emit [part_line, next_event_line)
            next_line = (events[k + 1][0] if k + 1 < len(events)
                         else (thesis.backmatter or thesis.end_document))
            out.extend(L[obj['line']:next_line])
        else:  # chapter
            ch_idx = obj
            if ch_idx not in wanted_ch_indices:
                continue
            ch = thesis.chapters[ch_idx]
            # Force chapter number
            if ch_idx == thesis.bio_chapter_idx:
                out.append(f"\\setcounter{{chapter}}{{{ch['number'] - 1}}}\n")
                ch_start, ch_end = thesis.chapter_range(ch_idx)
                out.extend(L[ch_start:ch_end])
                continue
            spec = wanted['main_chapters'][ch_idx]
            out.append(f"\\setcounter{{chapter}}{{{ch['number'] - 1}}}\n")
            if spec == 'all':
                ch_start, ch_end = thesis.chapter_range(ch_idx)
                out.extend(L[ch_start:ch_end])
            else:
                intro_start, intro_end = thesis.chapter_intro_range(ch_idx)
                out.extend(L[intro_start:intro_end])
                secs = ch['sections']
                for sec_num in sorted(spec):
                    sec_idx = sec_num - 1
                    if not (0 <= sec_idx < len(secs)):
                        raise ValueError(
                            f"Section {ch['number']}.{sec_num} not found "
                            f"(chapter {ch['number']} has {len(secs)} sections)")
                    # Force section number so e.g. 9.3 stays labeled 9.3
                    out.append(f"\\setcounter{{section}}{{{sec_num - 1}}}\n")
                    s_start, s_end = thesis.section_range(ch_idx, sec_idx)
                    out.extend(L[s_start:s_end])

    # 11. Backmatter + bibliography
    if wanted['references']:
        if thesis.backmatter is not None and thesis.end_document is not None:
            out.extend(L[thesis.backmatter:thesis.end_document])

    # 12. \end{document}
    out.append(L[thesis.end_document])
    return ''.join(out)


# --- Config file ------------------------------------------------------------

def parse_config(path):
    """Parse a simple 'name = part1, part2, ...' config file."""
    variants = []
    for lineno, raw in enumerate(Path(path).read_text().splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if '=' not in line:
            raise ValueError(f"{path}:{lineno}: expected 'name = parts', got: {raw!r}")
        name, parts_str = line.split('=', 1)
        name = name.strip()
        parts = [p.strip() for p in parts_str.split(',') if p.strip()]
        variants.append((name, parts))
    return variants


# --- Compilation ------------------------------------------------------------

def compile_pdf(tex_file: Path, quiet=True):
    """Compile a .tex file to PDF using latexmk (preferred) or pdflatex."""
    tex_dir = tex_file.parent
    name = tex_file.stem
    if shutil.which('latexmk'):
        cmd = ['latexmk', '-pdf', '-interaction=nonstopmode',
               '-halt-on-error', '-f', tex_file.name]
    elif shutil.which('pdflatex'):
        # Fallback: pdflatex -> bibtex -> pdflatex -> pdflatex
        steps = [
            ['pdflatex', '-interaction=nonstopmode', tex_file.name],
            ['bibtex', name],
            ['pdflatex', '-interaction=nonstopmode', tex_file.name],
            ['pdflatex', '-interaction=nonstopmode', tex_file.name],
        ]
        for step in steps:
            subprocess.run(step, cwd=tex_dir,
                           stdout=subprocess.DEVNULL if quiet else None,
                           stderr=subprocess.DEVNULL if quiet else None)
        return (tex_dir / f"{name}.pdf").exists()
    else:
        print("  ! No LaTeX engine found (install latexmk or pdflatex). "
              "Emitted .tex only.", file=sys.stderr)
        return False

    result = subprocess.run(cmd, cwd=tex_dir,
                            stdout=subprocess.DEVNULL if quiet else None,
                            stderr=subprocess.DEVNULL if quiet else None)
    return (tex_dir / f"{name}.pdf").exists()


# --- Main --------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--source', default='main.tex',
                    help='Path to main.tex (default: main.tex)')
    ap.add_argument('--config', default='variants.conf',
                    help='Config file listing variants (default: variants.conf)')
    ap.add_argument('--output-dir', default='variants',
                    help='Where to write variant .tex and .pdf files '
                         '(default: ./variants/)')
    ap.add_argument('--name', default=None,
                    help='Build a single ad-hoc variant with this name. '
                         'Must be used together with --parts. '
                         'Skips the config file.')
    ap.add_argument('--parts', default=None,
                    help='Comma-separated parts for the ad-hoc variant. '
                         'E.g. "title,keywords,abstract,1,9.1"')
    ap.add_argument('--no-compile', action='store_true',
                    help='Emit .tex files only; do not run LaTeX')
    ap.add_argument('--verbose', action='store_true',
                    help='Show LaTeX output on stdout')
    ap.add_argument('--archive-url', default=DEFAULT_ARCHIVE_URL,
                    help=f'URL printed on the abridged-variant cover page '
                         f'(default: {DEFAULT_ARCHIVE_URL})')
    ap.add_argument('--no-cover', action='store_true',
                    help='Never add a cover page (even for abridged variants)')
    ap.add_argument('--force-cover', action='store_true',
                    help='Always add a cover page (even for the full variant)')
    args = ap.parse_args()

    source = Path(args.source).resolve()
    if not source.is_file():
        sys.exit(f"Can't find source file: {source}")
    out_root = Path(args.output_dir).resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    text = source.read_text()
    thesis = Thesis(text.splitlines(keepends=True))

    if args.name:
        if not args.parts:
            sys.exit("--name requires --parts")
        variants = [(args.name, [p.strip() for p in args.parts.split(',') if p.strip()])]
    else:
        cfg = Path(args.config)
        if not cfg.is_file():
            sys.exit(f"Config file not found: {cfg}  "
                     "(pass --config, or use --name/--parts for a one-off)")
        variants = parse_config(cfg)

    project_dir = source.parent
    for name, parts in variants:
        print(f"→ {name}: {', '.join(parts)}")
        wanted = resolve_wanted(parts, thesis)

        # Decide whether this variant gets a cover page.
        if args.force_cover:
            add_cover = True
        elif args.no_cover:
            add_cover = False
        else:
            add_cover = not is_full_variant(parts)

        cover_tex = (build_cover_page_tex(wanted, thesis, args.archive_url)
                     if add_cover else None)
        tex_content = assemble_tex(thesis, wanted, cover_page_tex=cover_tex)

        variant_dir = out_root / name
        variant_dir.mkdir(parents=True, exist_ok=True)
        # Mirror project files into variant_dir via symlinks (cls, bib, figs, etc.)
        for item in project_dir.iterdir():
            if item.name in {out_root.name, '.git', '__pycache__'}:
                continue
            if item.resolve() == source.resolve():
                continue
            link = variant_dir / item.name
            if link.exists() or link.is_symlink():
                continue
            try:
                link.symlink_to(item.resolve())
            except OSError:
                # Fallback to copy on systems without symlinks
                if item.is_dir():
                    shutil.copytree(item, link)
                else:
                    shutil.copy2(item, link)

        tex_file = variant_dir / f"{name}.tex"
        tex_file.write_text(tex_content)
        print(f"   wrote {tex_file.relative_to(Path.cwd())}")

        if not args.no_compile:
            ok = compile_pdf(tex_file, quiet=not args.verbose)
            pdf_file = variant_dir / f"{name}.pdf"
            if ok and pdf_file.exists():
                # Also copy the PDF up to out_root for easy access
                shutil.copy2(pdf_file, out_root / f"{name}.pdf")
                print(f"   built  {(out_root / (name + '.pdf')).relative_to(Path.cwd())}")
            else:
                print(f"   ! PDF not produced (check {variant_dir}/{name}.log)")


if __name__ == '__main__':
    main()

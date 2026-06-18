# Summary of Dissertation Revisions

## At a Glance

- Chapter 2 (Background & Related Work) fully rewritten as one overall narrative, roughly 4,700 words, with detailed related work kept in each body chapter. Complete overhaul and avoids overlapping with chapter content on related work.
- Technical depth added to Data Navigator, Skeleton, Cross-Perception, and Softerware.
- New Conclusion chapter (Chapter 9, "Findings") inserted before Discussion & Future Work, synthesizing across chapters.
- All `[REDACTED]` markers resolved.
- Bibliography overflow fixed (the `xurl` package now breaks long URLs).

## Jen

Wanted:
- Clarify the technical contributions.
- Clarify what is in the library vs the demos for Data Navigator.
- Give related work a clear goal, cut repeated paragraphs, fix the "too rapid-fire for a beginner, too sparse for an expert" problem, add missing relevant work.
- Fix the `[REDACTED]` markers.
- One coherent overall related work plus detailed per-chapter related work, with signposting; the takeaway should be that the thesis work is inevitable.

Done:
- Chapter 2 rewritten into a single overall narrative (Sections 2.1 to 2.5, ~4,700 words); per-chapter related work retained and no longer duplicated up front.
- New structure: how tools shape practitioners (2.1), the accessibility and visualization conversation and its research vs practice split (2.2), critical and peripheral voices (2.3), the argument for the three problem areas (2.4), and a closing "What to Take Away" (2.5).
- Data Navigator gained an explicit library-vs-demos boundary (5.9.1) and an expanded System Design section (5.5).
- The Findings chapter opens by restating the Chapter 2 gap, tying the inevitability framing across the thesis.
- All `[REDACTED]` markers removed.

## Patrick

Wanted:
- The thesis felt like a staple job; Chapter 9 was too future-focused; add a conclusion chapter.

Done:
- Transitions added before and after each chapter.
- New Chapter 9 ("Findings") inserted before Discussion & Future Work (now Chapter 10).
- Seven synthesis findings, each traceable to body-chapter results:
  - 9.1 Barriers are produced for practitioners, with and without disabilities.
  - 9.2 Tools can reduce the work required to make things accessible.
  - 9.3 Making the invisible structurally visible changes practice.
  - 9.4 Friction from a tool can be productive.
  - 9.5 Tool-use and tool-making are generative.
  - 9.6 The hardest barriers required intervention at the substrate.
  - 9.7 What tool-making did not do (adoption, access friction, authorship).
- Speculative ideas were routed to the Discussion rather than asserted as findings.

## Dom

Wanted:
- Related work on sonification.
- Policy, and why future policy might drive adoption of these tools.
- Investigate the shift in research.
- Unpack why navigation, interaction, and personalization are the priorities.

Done:
- Generally, all comments in the doc were engaged and resolved.
- Sonification covered in the history-across-modalities section (2.2.1) and recurring through the draft.
- Research vs practice shift argued in 2.2.2 and 2.2.3.
- The three problem areas argued explicitly in Section 2.4 and carried into the substrate finding (9.6).

## Tamara

Wanted:
- Chapter 3 persona switch.
- A bibliography fix pass.
- Clarify what the Softerware tool actually is; document the tool and the taxonomy.

Done:
- Softerware now documents both the tool and the taxonomy: 195 option categories and 774 option choices, reduced to the 33-category, 137-option study subset.
- Study subset is in Table 8.1; the complete set is reproduced in the appendix ("The Softerware Option Taxonomy").
- New subsection 8.6.4 ("What the Prototype Actually Is") states plainly what the prototype implements.
- Bibliography overflow fixed via `xurl`.

Still pending (handled separately):
- Chapter 3 persona pass.

## Ken

Wanted:
- Be clearer about Skeleton as a design probe vs a tool; say what the probe makes visible upfront.
- Discuss future directions and other scenarios; clarify design implications.
- Clarify how Skeleton sits in the related work.

Done:
- Skeleton framed explicitly as a design probe (introduced in 6.5, revisited in the limitations at 6.9 and 6.10), with its purpose stated as making non-visual navigation structure legible.
- System Design (6.6) details the Staging, Edit, and Test workflow plus the Inspector and the Dimensions API.
- Design implications and other scenarios addressed in 6.9.5.
- Chapter related work (6.4) situates Skeleton against visualizing non-visual structure, non-visual data experiences, and authoring.

## Cross-Perception (technical depth and schematic)

Done:
- Wiring schematic added (Figure in 7.6.2) with full alt text.
- "Electronics and firmware" passage documents the Behringer MF100T faders, Teensy 4.0, and DRV8833 driver: wiper position on A0/A2, touch-sense on A1/A3, motor-direction pins D2 to D5, USB-powered 5V motor supply, touch-detection method, and the serial command protocol. Checked against the firmware and datasheets.
- The two prototype URLs now point to live OSF links (replacing `[REDACTED]`).
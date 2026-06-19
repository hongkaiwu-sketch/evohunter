# Design

## Visual Theme

EvoHunter uses a restrained product UI: white workspace, quiet neutral panels, and a burnt-amber primary color for key actions and active state. The mood is a clinical recruiting workbench with one warm signal color, not a brand-heavy dashboard.

## Color Tokens

```css
:root {
  --color-bg: oklch(1 0 0);
  --color-surface: oklch(0.975 0 0);
  --color-panel: oklch(0.948 0 0);
  --color-ink: oklch(0.205 0.018 65);
  --color-muted: oklch(0.455 0.018 65);
  --color-border: oklch(0.875 0 0);
  --color-primary: oklch(0.58 0.165 38);
  --color-primary-hover: oklch(0.52 0.17 38);
  --color-accent: oklch(0.38 0.095 178);
  --color-success: oklch(0.52 0.12 150);
  --color-warning: oklch(0.68 0.14 72);
  --color-error: oklch(0.55 0.17 28);
}
```

## Typography

Use `system-ui`, `-apple-system`, `BlinkMacSystemFont`, and `Segoe UI`. Keep a fixed product scale: 12px captions, 14px supporting UI, 16px body, 18px section headings, 24px page heading. Use tabular numbers for scores and generations.

## Layout

The workbench uses three structural regions on desktop:

1. Workflow rail for step context.
2. Main input and parsing area.
3. Results inspector for rankings, JSON, and feedback.

On tablet and mobile, regions stack into a single column with the workflow rail becoming a horizontal step bar.

## Components

Primary controls are solid amber buttons with white text. Secondary controls use neutral outlines. Forms always use visible labels and inline help. Downstream actions stay disabled until the required parsed data exists. Results use tables for comparison, score chips for dimension detail, and code blocks for JSON inspection. Cards are only used for distinct tool panels and never nested.

## State Model

The workflow rail uses active, completed, and error states. A successful JD parse completes `JD` and activates `Genes`; candidate parsing completes `Genes` and activates `Rank`; scoring completes `Rank` and activates `Evolve`; feedback evolution completes `Evolve`. Status text must explain the current action or error without relying only on color.

## Motion

Use short 150-200ms transitions for hover, focus, loading, and panel state changes. Respect `prefers-reduced-motion` by disabling nonessential transitions.

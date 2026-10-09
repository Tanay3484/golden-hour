# 003 — Visual redesign: Requirements

- **Status:** Approved (2026-10-10)
- **Owner:** @Tanay3484
- **Why now:** the owner's review on 2026-10-10: the UI "looks like a quick 30-minute project". The judges'
  first impression is the live page.

## Goal

Make Golden Hour look and feel like a real product, without changing what it does or how it protects
privacy.

## Acceptance criteria

- V1 **Layout:** two columns on screens ≥ 960 px wide (planner left, results right; the planner stays in
  view while scrolling), one column below that. No horizontal scrolling at 360 px.
- V2 **Structure:** a top bar (brand, °C/°F control, source link), a short intro, numbered planner steps
  (location → free time → interests), and an empty state that explains what you'll get before the
  first search.
- V3 **Results:** the chosen window shows a score ring, weather stat tiles, a sunrise-to-sunset timeline
  marking golden hour and every candidate window, and the candidate windows as selectable options.
- V4 **Places:** category icons and colours, walking time, a Map button, skeleton placeholders while
  loading, and the OSM attribution (R8.5).
- V5 **Visual system:** SVG icons instead of emoji; one set of colour tokens with full light and dark
  themes; visible focus states; reduced-motion respected.
- V6 **No regressions:** every 001/002 behaviour and element ID still works. The Python tests, the Node
  test, and the three browser journeys (Pune, Berlin dark, OSM down) pass.
- V7 **Privacy and weight:** no web fonts or third-party assets (they would leak visitors' IPs); page
  weight stays under 200 KB (N3).

## Non-goals

- New features, copy rewrite beyond labels, a manual theme switch, animations beyond small transitions.

## Changelog

- 2026-10-10 — Initial draft, written alongside a prototype on `spike-003-redesign` (screenshots in
  `screens/`).

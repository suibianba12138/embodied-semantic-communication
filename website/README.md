# Website V1 — synchronized experiment replay

This is a **static, evidence-linked demonstration**, not an interactive MuJoCo simulator and not a radio link. The videos are actual recorded MuJoCo runs; telemetry is loaded from the corresponding recorded trace.

## Preview locally

From the repository root:

```bash
python -m http.server 8000 --directory website
```

Open **http://localhost:8000/**. Do not open the HTML through `file://`: JSON `fetch()` requests need an HTTP origin.

No npm install, build step or backend is required. The website uses standard HTML, CSS, and JavaScript. Fonts are loaded from Google Fonts when online, with local system fallbacks.

## Structure

- `index.html` — full landing page and accessible replay UI.
- `css/styles.css` — responsive design (desktop, tablet and mobile).
- `js/app.js` — run selection, video ↔ trace synchronization, receive-event log, telemetry, and heading plot.
- `assets/video/` — four compressed versions of the verified P3-S1-V2 runs.
- `assets/img/` — scene views and P1/P2 communication figures.
- `assets/data/` — three exported, corresponding 50 Hz tick and 10 Hz link-event records.

The canonical file/provenance mapping and SHA256 checks are in the repository-root `WEBSITE_MEDIA_MANIFEST.json`.

## Synchronization and trace integrity

The source exporter maps video frame `i` to original 50 Hz policy trace row `i × 2`. Video frame rate is 25 fps. Each `video_clock.frame_map` entry stores `video_time_s`, `trace_index`, and `sim_time_s`. The UI uses this mapping rather than pretending that all runs have the same duration.

- Ideal and noiseless runs have 658 video frames / 26.32 s and 527 link events.
- The 8 dB AWGN run has 656 frames / 26.24 s and 525 link events, of which **11 were rejected**.
- Rejection buttons seek to the first video frame at or following the recorded simulation reception time.
- Only values actually stored in the trace can be displayed. An unavailable target observation is shown as “—”.
- The heading plot is computed from recorded yaw angles with unwrap for visualization; it does not alter any simulation data.
- QPSK constellation in the physical-layer explainer is explicitly marked *schematic*. Separate P1 figures show actual numerical PHY measurements.

The main video in each run retains the recorded caption overlay. The optional first-person split view uses the **same** 8 dB run; its original camera resolution is 64 × 48.

## Quick browser acceptance checks

1. Load page over `http://localhost:8000`; verify the hero movie and all four P1/P2/scene figures are visible.
2. Select **AWGN · 8 dB**, wait for the trace-loaded status, and confirm “11 rejects” and 11 seekable event buttons.
3. Click an error chip: video should seek to its timestamp and display receiver status/history; pause/play and use the native seek bar.
4. Switch to **Noiseless QPSK** or **Ideal**: both must show zero rejected events.
5. Switch back to AWGN; toggle the **robot camera** split view and back without mixing trace data.
6. Test at 320 px, phone, tablet, desktop; check keyboard navigation, focus outlines, and reduced-motion behavior.
7. In dev tools, verify that the data fetches are from the corresponding `website/assets/data/*.json` paths. The UI does not fetch raw `artifacts/` traces or ask for external API credentials.

### Known limits

- This first implementation has been written and reviewed through the GitHub connector. **Browser-level visual acceptance remains necessary**, especially checks 1–7 above.
- Media and JSON were pre-verified by the local asset preparation process. The browser replay still depends on their HTTP availability.
- The results concern one fixed industrial layout, one G1 scenario and one communication seed. The clear route does **not** demonstrate collision avoidance or planning.
- QPSK is simulated with ideal synchronization and AWGN; this project does not claim on-air transmission.
- The robot runtime depends on external V1.1/Candidate B software and model assets, which are **not** included. Robot full-stack reproduction is not supported by this media-only public candidate set.
- Model/asset licenses and public redistribution of screenshots/videos have not been cleared. **Keep this repository private and do not enable GitHub Pages until rights are reviewed.**

## Git branch handoff

The first website implementation lives on `feature/website-replay-v1` for review. The validated research baseline remains on `main`. Do not merge or publish merely to view the site. Later updates to local copies can use `git fetch origin` and `git switch feature/website-replay-v1` from a clean working tree, or a fresh clone into a separate directory.

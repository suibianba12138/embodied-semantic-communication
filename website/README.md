# Embodied Semantic Communication — Project Website

The website is an academic project page featuring a **time-synchronized replay of recorded G1 MuJoCo motion and QPSK packet transmission**. All changing communication states, transmitted/received bits, error counts and robot commands come from the same fixed experiment trace as the selected video.

## Start locally

```bash
python -m http.server 8000 --directory website
# Open http://localhost:8000/
```

No build tools, npm packages or backend services are required. Do not open `index.html` through `file://`: it loads linked JSON over HTTP.

## Page structure

- Introductory abstract, links and verified robot scene.
- **Robot Motion × Communication Replay:** 720p video, 10 Hz OBS/CMD events, link directions, 96-bit TX/RX fields, bit mismatches, frame accept/reject status, controller state, target range, heading and applied command.
- Original PHY illustrations: QPSK BER, RRC PSD, passband waveform/constellation.
- Verified P3-S1-V2 experiment table and limitations.

**Experiment choices:** ideal scheduled messages, noiseless QPSK and QPSK with 8 dB AWGN. They are **different complete real MuJoCo episodes** in the same fixed layout, not a single run with channel switching.

## How synchronization works

The local exporter preserves `video_clock.frame_map`: video frame `i` corresponds to trace policy step `2i`, with `sim_time_s = trace.time_s − 0.02s`. The video rate is 25 fps, policy rate 50 Hz and communication 10 Hz. The replay converts media time to the trace row using the explicit frame map.

- Links show the **most recently received** OBS and CMD statuses.
- The packet inspector shows recorded `tx_bits` / `rx_bits` (96 bits each), with bit mismatches highlighted.
- Recorded TX/RX timestamps are used to label reception and time difference.
- On-screen packet markers highlight the latest received event for a brief visual interval; that visual interval is **not** claimed to be the physical airtime of a QPSK packet.
- Clicking a CRC/preamble rejection seeks to the nearest video frame and opens that exact recorded frame in the packet inspector.
- The 8 dB trace contains exactly **11 rejected frames** (7 CRC, 4 preamble); the other two traces have zero rejects.
- No data are fabricated to fill observations where the target is invalid.

## Site evidence

| Condition | Video | Trace | Duration |
| --- | --- | --- | ---: |
| Ideal | `assets/video/industrial-ideal.mp4` | `assets/data/ideal.json` | 26.32 s |
| Noiseless QPSK | `assets/video/industrial-noiseless.mp4` | `assets/data/noiseless.json` | 26.32 s |
| 8 dB QPSK/AWGN | `assets/video/industrial-awgn-8db.mp4` | `assets/data/awgn-8db.json` | 26.24 s |

All derived media have source/export paths and SHA256 hashes in the root `WEBSITE_MEDIA_MANIFEST.json`. The optional split view is `assets/video/industrial-awgn-8db-split.mp4`; camera images were originally 64 × 48, rendered larger for presentation.

## Browser checks

1. Serve over HTTP. Verify the abstract, method diagrams, real figures and G1 scene render.
2. Select AWGN; packet view should show exactly 96 TX and 96 RX bits and 11 selectable rejection events.
3. Play, pause and scrub. Robot state, packet inspector and 10 Hz link statuses should follow the selected video time.
4. Select a rejection; inspect the altered bits and CRC/preamble reason. Check that the seeked media time approximately matches the event timestamp.
5. Switch ideal/noiseless/AWGN. Ensure no data from one condition appear under another.
6. Toggle first-person split video in the 8 dB condition.
7. Check mobile widths and browser console for layout and resource errors.

## Scope and rights

This is **recorded, trace-driven visualization** of numerically simulated QPSK/robot behavior. It does not transmit new RF frames, connect to an actual G1 or run MuJoCo in the browser. The scenes show obstacles in a predetermined clear route, not newly developed obstacle avoidance.

The full robot runtime and model meshes/ONNX are not shipped in this repository. Redistribution permissions for G1-derived public videos/screenshots and the project license remain unresolved. **Do not publicly activate Pages until permissions have been checked.**

# Embodied Semantic Communication

**From bits to motion.** A course-design research prototype joining a numerically implemented QPSK digital communication system, compact task-oriented semantic messages, and recorded closed-loop Unitree G1 navigation in MuJoCo.

> **Status:** P1/P2 communication tests validated; P3 and P3-S1-V2 bounded MuJoCo showcase validated. The full robot runtime and third-party model assets are not included in this repository. This repository is currently **private**, and permissions for public distribution of G1-related media/assets remain under review.

## Website preview

The experimental showcase includes a synchronized, timestamp-linked replay, three tested communication conditions, QPSK theory/experiment figures, and recorded robot telemetry.

**[Open website source](website/)** · **[Local preview instructions](website/README.md)**

```bash
python -m http.server 8000 --directory website
# visit http://localhost:8000/
```

The website is a static browser experience. It does not run MuJoCo or RF hardware.

## The system

```text
G1 RGB-D (64 × 48)
   → task-specific target observation (OBS)
   → 96-bit wire frame + CRC-16
   → Gray QPSK / RRC / AWGN / matched-filter reception (10 Hz simulated uplink)
   → edge SEARCH / ALIGN / APPROACH / STOP controller
   → 96-bit velocity command (CMD)
   → QPSK downlink (10 Hz)
   → existing G1 ONNX locomotion policy (50 Hz)
   → MuJoCo physics and new camera observation
```

**PHY:** 4,800 symbols/s; 9,600 bit/s; sample rate 76.8 kHz; 16 samples/symbol; 161-tap, unit-energy RRC with roll-off 0.35. The independent passband verification generates a 20 kHz numerical carrier. The G1 closed-loop communication simulation uses the validated complex-baseband QPSK/AWGN implementation.

**Wire v1:** a 96-bit packet comprises 16-bit preamble, 12-bit header, 52-bit payload and 16-bit CRC. OBS carries a color target's validity, range, bearing and time; CMD carries motion velocities, TTL and a mode. These are task-specific structured messages, *not* reversible image compression and *not* a learned end-to-end semantic codec.

**Robot:** existing color/depth detector, finite-state target controller and Candidate B locomotion policy. This project does not train a new robot controller or implement natural-language VLA.

## Verified fixed-layout industrial showcase

The final scene contains six distinct industrial prop groups represented by **22 collidable + 20 visual MuJoCo primitives**. The red target begins outside the camera field of view. Search, turn, reacquisition, approach and stop are recorded from a real MuJoCo simulation (not keyframed animation).

| Communication condition | Task | Duration | Path length | BER | Received frames |
| --- | --- | ---: | ---: | ---: | ---: |
| Ideal scheduled messages | Success | 26.32 s | 3.207 m | N/A | 527 / 527 |
| Full QPSK, noiseless | Success | 26.32 s | 3.209 m | 0 / 50,592 | 527 / 527 |
| Full QPSK, 8 dB AWGN | Success | 26.22 s | 3.202 m | 11 / 50,400 | 514 / 525 |

The 8 dB run had **11 rejected frames** (7 CRC rejections and 4 preamble rejections), with no observed obstacle contact or fall in the reported traces. The scene leaves a clear route: **this is not an autonomous obstacle-avoidance demonstration**. Single-layout, single-seed evidence is not general robustness validation.

**[Experiment report](P3_S1_V2_INDUSTRIAL_SHOWCASE_REPORT.md)** · **[Media provenance and SHA256 manifest](WEBSITE_MEDIA_MANIFEST.json)**

## Core implementation

| Path | Purpose |
| --- | --- |
| `src/esc/phy.py` | Gray QPSK, RRC TX/RX, AWGN, real-passband demonstration and BER utilities |
| `src/esc/frame.py` | 96-bit OBS/CMD framing, quantization, CRC-16 and receive validation |
| `src/esc/p3_link.py` | Communication helper for the G1 closed-loop experiment |
| `src/esc/p3_s1_scene.py` | Industrial scene geometry and deterministic placement |
| `experiments/p1_phy.py` | Independent PHY numerical validation and scientific plots |
| `experiments/p2_semantic.py` | Task-message framing and error-performance experiment |
| `tests/` | Unit and experiment regression tests |
| `website/` | Static showcase and synchronized replay |

Some P3 G1 runner scripts are intentionally excluded from the initial Git whitelist because they contain machine-specific absolute paths and depend on external software; a fully portable G1 reproduction guide has not yet been prepared. Do not mistake the website replay for a stand-alone robot simulator.

## Reproduce the independent communication layer

Create an isolated Python environment and install the versions in `requirements-p1.txt`, then run:

```bash
PYTHONPATH=src pytest -q tests/test_phy.py
MPLCONFIGDIR=/tmp/p1_mpl_cache PYTHONPATH=src python experiments/p1_phy.py \
  --config experiments/p1_phy_config.json --output artifacts/p1_phy
```

P2 scripts and tests are present. Full G1 experiments require an appropriately configured external V1.1/MJLab/MuJoCo/Candidate B environment and model permissions.

**[PHY implementation report](P1_PHY_IMPLEMENTATION_REPORT.md)** · **[PHY reproduction notes](P1_PHY_README.md)**

## Interpretation and limitations

- This is a numerical digital link with ideal known carrier/timing/frame synchronization, not wireless hardware.
- The optional 20 kHz real-passband verification is independent of the baseband PHY used by the actual robot closed loop.
- All G1 results shown here are from a single fixed industrial layout and single channel seed per condition.
- Obstacles are physically collidable but do not force autonomous route planning; no generalized avoidance claim is made.
- Original project licensing and third-party Unitree G1-related model, policy and media/derivative rights require review before any public distribution. No license is granted merely because code appears in this repository.

## Provenance

The website's image and video exports are paired with exact original-run hashes in `WEBSITE_MEDIA_MANIFEST.json`. The compressed browser traces contain the original per-policy-tick and per-link-event data needed for synchronized playback, including every rejected frame. Raw experiment archives and proprietary/third-party robot assets remain outside the tracked repository.

*Prepared November 2026 · UESTC communication systems / embodied robotics course design.*

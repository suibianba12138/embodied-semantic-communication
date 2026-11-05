# P3-S1-V2 Industrial Laboratory Scene Design

## Goal and boundaries

Build an industrial robotics laboratory visual scene for the existing `B_-30deg_seed0` task. Keep the G1 model, Candidate B policy, V1.1 perception/controller, 64×48 RGB-D camera, QPSK PHY, and Wire v1 unchanged. Do not modify the legacy repository or claim obstacle avoidance.

## Scene architecture

Use six distinct native-primitive assemblies: a blue-gray multi-level rack; a dark teal control cabinet with a face panel and indicator details; mixed yellow/brown package stacks; a yellow/black guard rail; blue/steel drums with visual hoops; and a gray-white workbench with legs and equipment. Large structural bodies use collision; small trim and all floor markings/background elements are visual-only. Use materials/colors and simple floor lane markings, with background structure outside the robot reference path and target sight lines.

Keep the successful reference trace as the placement constraint. Preserve the original perception sensor. Create separate high-resolution third-person views for scene review and 1280×720 video, rendering each frame from live `env.sim.data` copied/synchronized to MuJoCo state. Do not read cached stale MuJoCo data. Keep all communication captions synchronized to the episode trace and retain the actual 64×48 first-person sensor frames where practical.

## Validation sequence

First render multiple MuJoCo camera angles and inspect object silhouettes, palette, robot/target visibility, and full travel-area framing. Then check collision masks, initial contacts and distances, unchanged RGB-D dimensions, and expected initial target invisibility. Only after those gates pass, run ideal messages, noiseless QPSK, then 8 dB AWGN in order, preserving traces, contact events, communication outcomes, and videos.

## Decision

Prefer native primitives and visual-only details over external meshes or fully collidable decorative detail. Keep the route open; this is a set-dressed obstacle-rich scene, not a navigation-policy upgrade.

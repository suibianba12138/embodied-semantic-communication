# Third-Party Notices and Public-Release Review

This repository contains original communication-system source code, selected experimental figures, recorded G1/MuJoCo simulation videos and their trace-linked JSON exports. It **does not** distribute G1 mesh files, the locomotion ONNX checkpoint or the external MJLab/V1.1 runtime.

## Upstream software

**Unitree Robotics — unitree_rl_mjlab**  
Repository: https://github.com/unitreerobotics/unitree_rl_mjlab  
Pinned upstream commit used as the audited robot asset/software reference: `1425b15f73bd4095f0df53709d7c389c3eb9e790`  
The upstream `LICENCE` file contains the **Apache License, Version 2.0**:  
https://github.com/unitreerobotics/unitree_rl_mjlab/blob/1425b15f73bd4095f0df53709d7c389c3eb9e790/LICENCE

**Google DeepMind — MuJoCo Menagerie / Unitree G1**  
Source: https://github.com/google-deepmind/mujoco_menagerie/tree/main/unitree_g1  
G1-specific `LICENSE` file: https://github.com/google-deepmind/mujoco_menagerie/blob/main/unitree_g1/LICENSE  
It contains Unitree Robotics' copyright notice (HangZhou YuShu TECHNOLOGY CO., LTD.) and a **three-clause BSD-style redistribution license**. The conditions require retaining the copyright notice, license conditions and disclaimer; the copyright holder's/contributors' names may not be used to imply endorsement without written permission. This project is independent and is **not endorsed by Unitree Robotics or Google DeepMind**.

### Asset provenance spot-check

At the pinned Unitree upstream commit, GitHub blob SHA matches the corresponding MuJoCo Menagerie G1 asset for the following source-file paths:

| G1 mesh | Matching Git blob SHA |
| --- | --- |
| `pelvis.STL` | `691a779b9c9f4c97f48eaa9edf9eb336ca3b4411` |
| `logo_link.STL` | `e9792098504b64b359fbffa983373e5e6fa1b50a` |
| `head_link.STL` | `2ee5fba15de3ccd4c31774bc7a66de7aeefab770` |
| `torso_link_rev_1_0.STL` | `8a759a709750ad97e1f372db0ebbff246daedcc1` |
| `left_shoulder_pitch_link.STL` | `e698311fb12d3f22f018b668c40dab667c39b8d3` |

This evidence establishes matching source assets for the five named files only, **not** a complete license audit of the original robot deployment, all meshes or the checkpoint.

## Original project code and media

The project's original code has **no chosen outbound LICENSE** at present. The repository owner should select a license only after verifying the ownership and contribution rights of each tracked module. Upstream materials retain their separate licenses regardless of the chosen license for original code.

The `website/assets/` videos and images are renderings of real MuJoCo simulations, not redistributed mesh assets. The permissions that govern public video distribution, logos and the precise recorded model have **not yet been conclusively audited**. Publicly distributing videos/screenshots should occur only after the full source and attribution chain is checked. The original ONNX policy is not shipped; its redistribution rights have not been checked.

The selected video is a **single fixed-layout navigation task with an unobstructed route**. No obstacle-avoidance or wireless-hardware claim is made.

## Publication gates

Before making the repository public or triggering GitHub Pages:

1. Confirm the applicable terms for the exact G1 model assets and policy used in the recorded videos, including any additional restrictions on screenshots/recordings or marks.
2. Retain the Unitree copyright, license conditions, disclaimer and any attribution/notice terms applicable to the assets actually used. Do not imply Unitree endorsement.
3. Decide original code licensing and obtain collaborator consent where required; add an appropriate `LICENSE` file only after this decision.
4. Complete browser-level checks of video/JSON synchronization, error-event seeking and responsive rendering. Static JS review alone is not browser validation.
5. Remember: a GitHub Pages website can be **public even when its repository is private**, depending on plan and feature settings. Do not deploy merely to test visibility.

This document is a provenance notice and audit record, **not** a new license for third-party content or a legal opinion.

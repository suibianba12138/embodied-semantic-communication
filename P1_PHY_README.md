# P1 QPSK Physical Layer

This P1 implementation follows `P0C_EMBODIED_SEMANTIC_COMM_FROZEN_SPEC.md`. It contains Gray QPSK mapping, a unit-energy 161-tap RRC filter, full-convolution TX/RX filtering, discrete complex-baseband and real-passband AWGN, ideal coherent passband downconversion, hard decisions, BER confidence bounds, Welch PSD, and reproducible plots.

P1 intentionally does not implement the P2 OBS/CMD wire protocol or connect MuJoCo/robot software.

## Environment

The validation environment used Python 3.13 and the exact packages listed in `requirements-p1.txt`. Install them in an isolated environment if they are not already present. The experiment does not require MuJoCo, Candidate B, or the old repository.

## Run tests

```bash
PYTHONPATH=src pytest -q tests/test_phy.py
```

## Regenerate experiments and figures

Matplotlib writes its cache under `/tmp` in the example below so no user-level configuration directory is needed:

```bash
MPLCONFIGDIR=/tmp/p1_mpl_cache PYTHONPATH=src \
  python experiments/p1_phy.py \
  --config experiments/p1_phy_config.json \
  --output artifacts/p1_phy
```

The checked-in experiment configuration fixes the master seed, Eb/N0 points, bit budgets, roll-off values, sample rate, carrier and chunk size. The JSON summary records the exact derived seed, number of compared bits, error count, empirical BER, theory BER and one-sided 95% upper confidence bound for every run. Filter metrics are also included.

## Outputs

- `artifacts/p1_phy/ber_theory_vs_simulation.png`: theory, complex baseband and real passband BER.
- `artifacts/p1_phy/rrc_rolloff_psd.png`: real passband PSD for roll-off 0.2, 0.35 and 0.5.
- `artifacts/p1_phy/passband_waveform_constellation.png`: 20 kHz real waveform and coherent receive constellation.
- `artifacts/p1_phy/p1_phy_summary.json`: measured results and numerical filter checks.
- `artifacts/p1_phy/p1_phy_config.json`: exact configuration copied by the run.

BER uses independently generated chunks. Ten symbols at each chunk boundary are excluded to remove the finite RRC cascade transient; the summary's `bits_compared` is the actual denominator. Zero observed errors, if any, are reported with a confidence bound and are never called BER=0.

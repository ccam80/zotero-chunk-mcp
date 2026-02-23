| Component | Runtime (µs) |
|---|---|
| Comb Filter (2nd order IIR) | 8.17 |
| Highpass Filter (2nd order IIR) | 5.88 |
| Lowpass Filter (1st order IIR) | 1.28 |
| Rectification and Smoothing | 2.62 |
| Total Signal Processing Chain Runtime | 17.95 |

| Implementation | Runtime (µs) |
|---|---|
| (i) Selected Lowpass Filter (1st order IIR) | 1.28 |
| (ii) Fixed-point Lowpass Filter (1st order IIR, direct form II) | 1.67 |
| (iii) Floating-Point Lowpass Filter (1st order IIR, direct form II) | 20.12 |
| (iv) Floating-Point Lowpass Filter (5th order FIR) | 49.80 |
| (v) Floating-Point Lowpass Filter (8th order FIR) | 73.60 |

# roland-emg-filter — Ground Truth Review

Paper: roland-emg-filter
Item key: Z9X4JVZ5
Total tables: 9 (1 artifact + 8 data)

---

## table_0 (p5) — ARTIFACT: unknown [0 cols × 0 rows]

- **Caption:** Uncaptioned table on page 5
- **Notes:** Artifact: diagram_as_table, not a data table. The image shows a block diagram (Figure 3) of the insulated EMG measurement set-up, followed by photographs (Figure 4). No tabular data present.
- **Verified:** false

(No table to render — headers and rows are empty.)

---

## table_1 (p7) — Table 1. Floating-point comb filter coefficients. [9 cols × 9 rows]

- **Caption:** Table 1. Floating-point comb filter coefficients.
- **Notes:** Filter names are in italic in the original. 'Che' = Chebyshev, 'But' = Butterworth. Dashes (-) indicate coefficients not applicable for 2nd-order filters (which have only a[0], a[200], a[400] and b[0], b[200], b[400]). The 3rd-order filter uses all coefficient positions.
- **Verified:** false

| Filter | a[0] | a[200] | a[400] | a[600] | b[0] | b[200] | b[400] | b[600] |
|---|---|---|---|---|---|---|---|---|
| 1 Hz Che | 1 | -1.8278 | 0.8501 | - | 1 | -2 | 1 | - |
| 3 Hz Che | 1 | -1.4449 | 0.6186 | - | 1 | -2 | 1 | - |
| 5 Hz Che | 1 | -1.0531 | 0.4665 | - | 1 | -2 | 1 | - |
| 7 Hz Che | 1 | -0.6680 | 0.3730 | - | 1 | -2 | 1 | - |
| 1 Hz But | 1 | -1.8227 | 0.8372 | - | 1 | -2 | 1 | - |
| 3 Hz But | 1 | -1.4755 | 0.5869 | - | 1 | -2 | 1 | - |
| 5 Hz But | 1 | -1.1430 | 0.4128 | - | 1 | -2 | 1 | - |
| 7 Hz But | 1 | -0.8252 | 0.2946 | - | 1 | -2 | 1 | - |
| 3rd order | 1 | 0 | 0 | 0 | 1 | -0.5 | -0.25 | -0.25 |

---

## table_2 (p10) — Table 2. Floating-point highpass filter coefficients. [7 cols × 18 rows]

- **Caption:** Table 2. Floating-point highpass filter coefficients.
- **Notes:** Filter names in italic. 'Che' = Chebyshev, 'But' = Butterworth. Image also contains Figure 8 (two frequency-response plots) below the table. The image rendering is small; some digit values may need verification against the original PDF.
- **Verified:** false

| Filter | a[0] | a[1] | a[2] | b[0] | b[1] | b[2] |
|---|---|---|---|---|---|---|
| 20 Hz Che | 1 | -1.9836 | 0.9839 | 1 | -2 | 1 |
| 30 Hz Che | 1 | -1.9754 | 0.9759 | 1 | -2 | 1 |
| 40 Hz Che | 1 | -1.9664 | 0.9674 | 1 | -2 | 1 |
| 50 Hz Che | 1 | -1.9580 | 0.9596 | 1 | -2 | 1 |
| 60 Hz Che | 1 | -1.9496 | 0.9518 | 1 | -2 | 1 |
| 70 Hz Che | 1 | -1.9418 | 0.9447 | 1 | -2 | 1 |
| 80 Hz Che | 1 | -1.9333 | 0.9370 | 1 | -2 | 1 |
| 90 Hz Che | 1 | -1.9247 | 0.9294 | 1 | -2 | 1 |
| 100 Hz Che | 1 | -1.9168 | 0.9225 | 1 | -2 | 1 |
| 20 Hz But | 1 | -1.9824 | 0.9825 | 1 | -2 | 1 |
| 30 Hz But | 1 | -1.9733 | 0.9737 | 1 | -2 | 1 |
| 40 Hz But | 1 | -1.9645 | 0.9651 | 1 | -2 | 1 |
| 50 Hz But | 1 | -1.9556 | 0.9565 | 1 | -2 | 1 |
| 60 Hz But | 1 | -1.9467 | 0.9481 | 1 | -2 | 1 |
| 70 Hz But | 1 | -1.9378 | 0.9397 | 1 | -2 | 1 |
| 80 Hz But | 1 | -1.9289 | 0.9314 | 1 | -2 | 1 |
| 90 Hz But | 1 | -1.9201 | 0.9231 | 1 | -2 | 1 |
| 100 Hz But | 1 | -1.9112 | 0.9150 | 1 | -2 | 1 |

---

## table_3 (p16) — Table 3. Poles of comb filters with quantized coefficients. [5 cols × 2 rows]

- **Caption:** Table 3. Poles of comb filters with quantized coefficients.
- **Notes:** The header row shows fC in italic. Column headers 1 Hz, 3 Hz, 5 Hz, 7 Hz are in bold.
- **Verified:** false

| fC | 1 Hz | 3 Hz | 5 Hz | 7 Hz |
|---|---|---|---|---|
| Chebyshev | 0.914 ± 0.119i | 0.723 ± 0.310i | 0.527 ± 0.435i | 0.335 ± 0.511i |
| Butterworth | 0.912 ± 0.077i | 0.738 ± 0.206i | 0.572 ± 0.292i | 0.413 ± 0.352i |

---

## table_4 (p18) — Table 4. Poles of highpass filters with quantized coefficients. [6 cols × 5 rows]

- **Caption:** Table 4. Poles of highpass filters with quantized coefficients.
- **Notes:** The table is split into two sub-sections: top rows cover 20-60 Hz (5 frequency columns), bottom rows cover 70-100 Hz (4 frequency columns). The second section repeats the fC / frequency header row (shown here as a data row per rule 6). 'Che' = Chebyshev, 'But' = Butterworth. The 100 Hz Che pole imaginary part reads 0.057i (same as 90 Hz Che).
- **Verified:** false

| fC | 20 Hz | 30 Hz | 40 Hz | 50 Hz | 60 Hz |
|---|---|---|---|---|---|
| Che | 0.992 ± 0.013i | 0.988 ± 0.020i | 0.984 ± 0.025i | 0.980 ± 0.032i | 0.976 ± 0.039i |
| But | 0.991 ± 0.007i | 0.987 ± 0.011i | 0.982 ± 0.015i | 0.978 ± 0.021i | 0.974 ± 0.025i |
| fC | 70 Hz | 80 Hz | 90 Hz | 100 Hz |  |
| Che | 0.972 ± 0.045i | 0.968 ± 0.051i | 0.964 ± 0.057i | 0.961 ± 0.057i |  |
| But | 0.969 ± 0.030i | 0.965 ± 0.033i | 0.960 ± 0.037i | 0.956 ± 0.041i |  |

---

## table_5 (p19) — Table 5. Runtime per sample of filters in C implementation at a 48 MHz clock. [2 cols × 5 rows]

- **Caption:** Table 5. Runtime per sample of filters in C implementation at a 48 MHz clock.
- **Notes:** The left column has no header label. The 'Total Signal Processing Chain Runtime' row is separated from the individual filter rows by a horizontal rule, indicating it is a summary/total row.
- **Verified:** false

|  | (µs) |
|---|---|
| Comb Filter (2nd order IIR) | 8.17 |
| Highpass Filter (2nd order IIR) | 5.88 |
| Lowpass Filter (1st order IIR) | 1.28 |
| Rectification and Smoothing | 2.62 |
| Total Signal Processing Chain Runtime | 17.95 |

---

## table_6 (p19) — Table 6. Comparison of runtime per sample of various lowpass-filter C implementa... [2 cols × 5 rows]

- **Caption:** Table 6. Comparison of runtime per sample of various lowpass-filter C implementations at a 48 MHz clock.
- **Notes:** The left column has no header label. Filter descriptions are right-aligned in the original. The caption in the GT template reads 'at a 48 MHz clock' (with 'a'); the paper caption on the image reads 'at 48 MHz clock' (partial, cut off at top of image).
- **Verified:** false

|  | (µs) |
|---|---|
| (i) Selected Lowpass Filter (1st order IIR) | 1.28 |
| (ii) Fixed-point Lowpass Filter (1st order IIR, direct form II) | 1.67 |
| (iii) Floating-Point Lowpass Filter (1st order IIR, direct form II) | 20.12 |
| (iv) Floating-Point Lowpass Filter (5th order FIR) | 49.80 |
| (v) Floating-Point Lowpass Filter (8th order FIR) | 73.60 |

---

## table_7 (p20) — Table 7. Effect of reducing sampling and clock frequency on power consumption an... [4 cols × 5 rows]

- **Caption:** Table 7. Effect of reducing sampling and clock frequency on power consumption and signal quality.
- **Notes:** Header 'Sampling Frequency fS (kHz)' uses subscript S in the original (fS). Header 'µC Clock Frequency (MHz)' uses the micro symbol (µC = microcontroller).
- **Verified:** false

| Sampling Frequency fS (kHz) | µC Clock Frequency (MHz) | Power Consumption (mW) | SNR |
|---|---|---|---|
| 10.0 | 48 | 31.5 | 12.6 |
| 5.0 | 16 | 20.5 | 12.6 |
| 2.0 | 8 | 15.9 | 11.2 |
| 1.0 | 4 | 14.4 | 10.1 |
| 0.5 | 2 | 13.7 | 7.8 |

---

## table_8 (p22) — Abbreviations [2 cols × 14 rows]

- **Caption:** Abbreviations
- **Notes:** The table has no visible header row in the original; column headers 'Abbreviation' and 'Meaning' are inferred from context. The section heading 'The following abbreviations are used in this manuscript:' appears above the table (partially visible at top of image). The µC entry uses the micro sign (µ).
- **Verified:** false

| Abbreviation | Meaning |
|---|---|
| ADC | Analog-to-digital conversion |
| BLE | Bluetooth Low Energy |
| DAC | Digital-to-analog converter |
| DSP | Digital signal processing |
| DC | Direct current |
| EMG | Electromyography |
| FDA | Filter Designer app |
| FIR | Finite impulse response |
| IIR | Infinite impulse response |
| µC | Microcontroller |
| OpAmp | Operational amplifier |
| PLI | Power-line interference |
| SNR | Signal-to-noise ratio |
| STFT | Short-time Fourier transform |

---

## Review Checklist

- [ ] table_0 — artifact confirmed
- [ ] table_1 — 9 rows, 9 cols verified
- [ ] table_2 — 18 rows, 7 cols verified
- [ ] table_3 — 2 rows, 5 cols verified
- [ ] table_4 — 5 rows, 6 cols verified
- [ ] table_5 — 5 rows, 2 cols verified
- [ ] table_6 — 5 rows, 2 cols verified
- [ ] table_7 — 5 rows, 4 cols verified
- [ ] table_8 — 14 rows, 2 cols verified

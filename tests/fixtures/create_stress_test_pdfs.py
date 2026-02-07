#!/usr/bin/env python3
"""
Generate stress test PDFs for section detection and extraction testing.

Run this script to create test fixtures in tests/fixtures/stress/

Usage:
    python tests/fixtures/create_stress_test_pdfs.py
"""
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak,
    Table, TableStyle, ListFlowable, ListItem
)
from reportlab.lib import colors

FIXTURES_DIR = Path(__file__).parent / "stress"


def create_academic_full():
    """
    PDF 1: Full Academic Paper Structure (sample_academic_full.pdf)

    10-15 pages with standard numbered sections:
    - Title page with author affiliations
    - Abstract
    - 1. Introduction
    - 2. Background
    - 3. Materials and Methods
    - 4. Results
    - 5. Discussion
    - 6. Conclusions
    - References
    - Appendix
    """
    doc = SimpleDocTemplate(
        str(FIXTURES_DIR / "sample_academic_full.pdf"),
        pagesize=letter,
        rightMargin=inch,
        leftMargin=inch,
        topMargin=inch,
        bottomMargin=inch
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Title'],
        fontSize=18,
        alignment=TA_CENTER,
        spaceAfter=12
    )
    heading_style = ParagraphStyle(
        'Heading1',
        parent=styles['Heading1'],
        fontSize=14,
        spaceBefore=18,
        spaceAfter=6
    )
    body_style = ParagraphStyle(
        'Body',
        parent=styles['Normal'],
        fontSize=11,
        alignment=TA_JUSTIFY,
        spaceAfter=12
    )
    abstract_style = ParagraphStyle(
        'Abstract',
        parent=styles['Normal'],
        fontSize=10,
        leftIndent=36,
        rightIndent=36,
        spaceAfter=12
    )

    story = []

    # Title page
    story.append(Spacer(1, 2*inch))
    story.append(Paragraph(
        "A Comprehensive Study of Heart Rate Variability<br/>in Autonomic Nervous System Assessment",
        title_style
    ))
    story.append(Spacer(1, 0.5*inch))
    story.append(Paragraph(
        "John A. Smith<sup>1</sup>, Jane B. Doe<sup>2</sup>, Robert C. Johnson<sup>1,3</sup>",
        ParagraphStyle('Authors', parent=styles['Normal'], alignment=TA_CENTER, fontSize=12)
    ))
    story.append(Spacer(1, 0.25*inch))
    story.append(Paragraph(
        "<sup>1</sup>Department of Biomedical Engineering, University of Example<br/>"
        "<sup>2</sup>School of Medicine, Example Medical Center<br/>"
        "<sup>3</sup>Institute for Advanced Research",
        ParagraphStyle('Affiliations', parent=styles['Normal'], alignment=TA_CENTER, fontSize=10)
    ))
    story.append(PageBreak())

    # Abstract
    story.append(Paragraph("ABSTRACT", heading_style))
    story.append(Paragraph(
        "Heart rate variability (HRV) provides a non-invasive window into autonomic nervous system "
        "function. This study examined the relationship between time-domain and frequency-domain HRV "
        "metrics across different physiological states. We recruited 150 healthy participants aged "
        "25-55 years and measured HRV during rest, mental stress, and physical exercise. Results "
        "showed significant correlations between RMSSD and high-frequency power (r=0.78, p<0.001), "
        "confirming parasympathetic origins. The LF/HF ratio increased during mental stress (p<0.01) "
        "but showed high inter-individual variability. These findings support the use of HRV as a "
        "biomarker for autonomic assessment while highlighting the need for standardized protocols.",
        abstract_style
    ))
    story.append(Spacer(1, 0.25*inch))
    story.append(Paragraph(
        "<b>Keywords:</b> heart rate variability, autonomic nervous system, parasympathetic, "
        "sympathetic, time-domain analysis, frequency-domain analysis",
        ParagraphStyle('Keywords', parent=styles['Normal'], fontSize=10)
    ))
    story.append(PageBreak())

    # 1. Introduction
    story.append(Paragraph("1. Introduction", heading_style))
    lorem = (
        "The autonomic nervous system (ANS) regulates involuntary physiological processes including "
        "heart rate, blood pressure, and digestion. Heart rate variability (HRV), the variation in "
        "time intervals between consecutive heartbeats, has emerged as a key indicator of ANS function. "
        "Since the landmark study by Akselrod et al. (1981), HRV analysis has been applied across "
        "cardiology, psychology, and sports science. "
    )
    for _ in range(4):
        story.append(Paragraph(lorem, body_style))
    story.append(PageBreak())

    # 2. Background
    story.append(Paragraph("2. Background", heading_style))
    story.append(Paragraph("2.1 Autonomic Nervous System", styles['Heading2']))
    for _ in range(3):
        story.append(Paragraph(
            "The sympathetic and parasympathetic branches of the ANS exert opposing effects on the "
            "sinoatrial node. Sympathetic activation increases heart rate through norepinephrine "
            "release, while parasympathetic (vagal) activation decreases heart rate via acetylcholine. "
            "This dual innervation allows rapid adjustment to physiological demands.",
            body_style
        ))

    story.append(Paragraph("2.2 HRV Metrics", styles['Heading2']))
    for _ in range(3):
        story.append(Paragraph(
            "Time-domain metrics include SDNN (standard deviation of NN intervals), RMSSD (root mean "
            "square of successive differences), and pNN50 (percentage of successive intervals differing "
            "by more than 50ms). Frequency-domain analysis using Fast Fourier Transform reveals power "
            "in very low frequency (VLF, 0.003-0.04 Hz), low frequency (LF, 0.04-0.15 Hz), and high "
            "frequency (HF, 0.15-0.4 Hz) bands.",
            body_style
        ))
    story.append(PageBreak())

    # 3. Materials and Methods
    story.append(Paragraph("3. Materials and Methods", heading_style))
    story.append(Paragraph("3.1 Participants", styles['Heading2']))
    story.append(Paragraph(
        "One hundred and fifty healthy volunteers (75 male, 75 female) were recruited from the local "
        "community. Inclusion criteria: age 25-55 years, no cardiovascular disease, no medications "
        "affecting heart rate. Exclusion criteria: diabetes, hypertension, BMI > 30 kg/m². The study "
        "was approved by the University Ethics Committee (Protocol #2023-001).",
        body_style
    ))

    story.append(Paragraph("3.2 ECG Recording", styles['Heading2']))
    story.append(Paragraph(
        "A three-lead ECG was recorded using Ag/AgCl electrodes (3M Red Dot 2560) at a sampling rate "
        "of 1000 Hz. Recordings were made using a Biopac MP160 data acquisition system with AcqKnowledge "
        "software (version 5.0). Electrode placement followed standard Lead II configuration.",
        body_style
    ))

    story.append(Paragraph("3.3 Protocol", styles['Heading2']))
    story.append(Paragraph(
        "Each participant completed three conditions: (1) 10-minute supine rest, (2) 5-minute mental "
        "arithmetic task (serial sevens), and (3) 5-minute moderate cycling at 60% predicted maximum "
        "heart rate. A 5-minute recovery period separated each condition.",
        body_style
    ))

    story.append(Paragraph("3.4 Data Analysis", styles['Heading2']))
    story.append(Paragraph(
        "R-peaks were detected using the Pan-Tompkins algorithm implemented in Python. Artefacts were "
        "removed using adaptive filtering with a threshold of 20% deviation from local mean. HRV metrics "
        "were computed using the hrv-analysis package (version 2.0). Statistical analysis was performed "
        "in R (version 4.2) using repeated-measures ANOVA with Bonferroni correction.",
        body_style
    ))
    story.append(PageBreak())

    # 4. Results
    story.append(Paragraph("4. Results", heading_style))
    story.append(Paragraph("4.1 Participant Characteristics", styles['Heading2']))

    # Add a results table
    table_data = [
        ['Characteristic', 'Mean ± SD', 'Range'],
        ['Age (years)', '38.2 ± 8.7', '25-55'],
        ['BMI (kg/m²)', '24.1 ± 3.2', '18.5-29.8'],
        ['Resting HR (bpm)', '68.4 ± 10.2', '48-92'],
        ['SDNN (ms)', '142.3 ± 45.6', '62-285'],
        ['RMSSD (ms)', '38.7 ± 18.4', '12-98'],
    ]
    table = Table(table_data, colWidths=[2.5*inch, 1.5*inch, 1.5*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    story.append(Paragraph("<b>Table 1:</b> Participant characteristics (N=150)", body_style))
    story.append(table)
    story.append(Spacer(1, 0.25*inch))

    story.append(Paragraph("4.2 HRV Changes Across Conditions", styles['Heading2']))
    story.append(Paragraph(
        "Significant differences in HRV metrics were observed across the three conditions "
        "(F(2,298)=45.7, p<0.001, partial η²=0.23). Post-hoc comparisons revealed that RMSSD "
        "decreased significantly from rest (38.7±18.4 ms) to mental stress (28.3±14.2 ms, p<0.001) "
        "and exercise (18.9±8.7 ms, p<0.001). The LF/HF ratio increased from 1.82±0.94 at rest to "
        "3.45±1.67 during mental stress (p<0.01).",
        body_style
    ))

    # Another table
    table_data2 = [
        ['Metric', 'Rest', 'Mental Stress', 'Exercise', 'p-value'],
        ['SDNN (ms)', '142.3±45.6', '98.4±32.1', '65.2±21.8', '<0.001'],
        ['RMSSD (ms)', '38.7±18.4', '28.3±14.2', '18.9±8.7', '<0.001'],
        ['LF (ms²)', '1245±567', '1678±734', '892±312', '<0.01'],
        ['HF (ms²)', '684±298', '486±234', '187±89', '<0.001'],
        ['LF/HF', '1.82±0.94', '3.45±1.67', '4.77±2.34', '<0.001'],
    ]
    table2 = Table(table_data2, colWidths=[1.2*inch, 1.1*inch, 1.1*inch, 1.1*inch, 0.8*inch])
    table2.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    story.append(Paragraph("<b>Table 2:</b> HRV metrics across conditions (mean±SD)", body_style))
    story.append(table2)
    story.append(PageBreak())

    # 5. Discussion
    story.append(Paragraph("5. Discussion", heading_style))
    for _ in range(5):
        story.append(Paragraph(
            "Our findings confirm that HRV metrics reflect autonomic modulation during different "
            "physiological states. The strong correlation between RMSSD and HF power supports the "
            "interpretation of these metrics as parasympathetic indices. However, the high variability "
            "in LF/HF ratio during mental stress suggests caution when using this metric as a marker "
            "of sympathovagal balance. Individual differences in stress reactivity may account for "
            "the observed variance.",
            body_style
        ))
    story.append(PageBreak())

    # 6. Conclusions
    story.append(Paragraph("6. Conclusions", heading_style))
    story.append(Paragraph(
        "This study demonstrates that HRV provides a reliable non-invasive assessment of autonomic "
        "function across different physiological states. Time-domain metrics, particularly RMSSD, "
        "show consistent patterns that reflect vagal tone. Frequency-domain analysis offers additional "
        "insights but requires careful interpretation, especially for the LF band and LF/HF ratio. "
        "Future research should focus on establishing normative values and standardizing measurement "
        "protocols to enhance clinical utility.",
        body_style
    ))
    story.append(Paragraph(
        "The findings have implications for clinical practice in cardiology, stress management, and "
        "sports medicine. HRV biofeedback interventions may benefit from targeting specific metrics "
        "based on individual baseline characteristics.",
        body_style
    ))
    story.append(PageBreak())

    # References
    story.append(Paragraph("References", heading_style))
    refs = [
        "1. Akselrod S, Gordon D, Ubel FA, et al. Power spectrum analysis of heart rate fluctuation: "
        "a quantitative probe of beat-to-beat cardiovascular control. Science. 1981;213(4504):220-222.",
        "2. Task Force of the European Society of Cardiology. Heart rate variability: standards of "
        "measurement, physiological interpretation and clinical use. Circulation. 1996;93(5):1043-1065.",
        "3. Shaffer F, Ginsberg JP. An overview of heart rate variability metrics and norms. "
        "Front Public Health. 2017;5:258.",
        "4. Berntson GG, Bigger JT Jr, Eckberg DL, et al. Heart rate variability: origins, methods, "
        "and interpretive caveats. Psychophysiology. 1997;34(6):623-648.",
        "5. Billman GE. The LF/HF ratio does not accurately measure cardiac sympatho-vagal balance. "
        "Front Physiol. 2013;4:26.",
    ]
    for i, ref in enumerate(refs[:20]):
        story.append(Paragraph(ref, body_style))
    # Add more dummy references
    for i in range(6, 35):
        story.append(Paragraph(
            f"{i}. Author{i} AB, Coauthor{i} CD. Title of paper number {i} examining cardiovascular "
            f"physiology and autonomic regulation. J Cardiol Res. {2010+i%15};{20+i}:{i*10}-{i*10+15}.",
            body_style
        ))
    story.append(PageBreak())

    # Appendix
    story.append(Paragraph("Appendix A: Supplementary Data", heading_style))
    story.append(Paragraph(
        "This appendix contains additional statistical analyses and raw data summaries that support "
        "the main findings presented in the Results section.",
        body_style
    ))
    story.append(Paragraph("A.1 Subgroup Analysis", styles['Heading2']))
    story.append(Paragraph(
        "When stratified by age group (25-39 vs 40-55 years), younger participants showed higher "
        "baseline RMSSD (42.3±19.8 vs 35.1±16.2 ms, p<0.05) but similar stress-induced changes.",
        body_style
    ))

    doc.build(story)
    print(f"Created: {FIXTURES_DIR / 'sample_academic_full.pdf'}")


def create_ambiguous_sections():
    """
    PDF 2: Ambiguous Section Names (sample_ambiguous_sections.pdf)

    8-10 pages with non-standard headings that should be mapped to standard sections.
    """
    doc = SimpleDocTemplate(
        str(FIXTURES_DIR / "sample_ambiguous_sections.pdf"),
        pagesize=letter,
        rightMargin=inch,
        leftMargin=inch,
        topMargin=inch,
        bottomMargin=inch
    )

    styles = getSampleStyleSheet()
    heading_style = ParagraphStyle(
        'Heading1',
        parent=styles['Heading1'],
        fontSize=14,
        spaceBefore=18,
        spaceAfter=6
    )
    body_style = ParagraphStyle(
        'Body',
        parent=styles['Normal'],
        fontSize=11,
        alignment=TA_JUSTIFY,
        spaceAfter=12
    )

    story = []

    # Preamble (no heading)
    story.append(Paragraph(
        "<b>Evaluating Novel Approaches to Cardiac Signal Processing</b>",
        ParagraphStyle('Title', parent=styles['Title'], fontSize=16, alignment=TA_CENTER)
    ))
    story.append(Spacer(1, 0.5*inch))
    story.append(Paragraph(
        "Anonymous Authors for Blind Review",
        ParagraphStyle('Author', parent=styles['Normal'], alignment=TA_CENTER)
    ))
    story.append(Spacer(1, 0.25*inch))

    # Ambiguous: "Experimental Approach" should map to methods
    story.append(Paragraph("I. EXPERIMENTAL APPROACH", heading_style))
    for _ in range(3):
        story.append(Paragraph(
            "The experimental approach employed in this study involves the collection of "
            "electrocardiogram (ECG) data from healthy volunteers under controlled conditions. "
            "Participants were instrumented with standard three-lead ECG electrodes and recordings "
            "were made at a sampling rate of 500 Hz using custom data acquisition hardware.",
            body_style
        ))
    story.append(PageBreak())

    # Ambiguous: "Findings" should map to results
    story.append(Paragraph("II. FINDINGS", heading_style))
    for _ in range(3):
        story.append(Paragraph(
            "The primary findings of this investigation demonstrate a significant relationship "
            "between signal quality and electrode impedance. Analysis of 200 recordings revealed "
            "that impedance values above 10 kOhm correlated with increased noise levels (r=0.67, "
            "p<0.001). Signal-to-noise ratio improved by 35% when impedance was maintained below "
            "5 kOhm through proper skin preparation.",
            body_style
        ))
    story.append(PageBreak())

    # Ambiguous: "III. RESULTS AND DISCUSSION" - compound heading, should map to results
    story.append(Paragraph("III. RESULTS AND DISCUSSION", heading_style))
    for _ in range(4):
        story.append(Paragraph(
            "The results indicate that our novel algorithm outperforms existing methods in terms "
            "of both accuracy and computational efficiency. The discussion of these results must "
            "consider the limitations of the dataset and the specific conditions under which "
            "testing was performed. Statistical analysis revealed significant improvements in "
            "detection sensitivity (p<0.01) while maintaining specificity above 95%.",
            body_style
        ))
    story.append(PageBreak())

    # Ambiguous: "Study Design and Implementation" should map to methods
    story.append(Paragraph("IV. STUDY DESIGN AND IMPLEMENTATION", heading_style))
    for _ in range(3):
        story.append(Paragraph(
            "The study design follows a randomized controlled approach with three experimental "
            "conditions. Implementation of the data collection protocol required careful attention "
            "to standardization across all recording sessions. Each participant underwent identical "
            "procedures to minimize confounding variables.",
            body_style
        ))
    story.append(PageBreak())

    # Ambiguous: "Data and Outcomes" should map to results
    story.append(Paragraph("V. DATA AND OUTCOMES", heading_style))
    story.append(Paragraph("5.1 Summary Statistics", styles['Heading2']))
    story.append(Paragraph(
        "Summary statistics for all outcome measures are presented in Table 1. The primary outcome "
        "showed significant improvement in the treatment group compared to control.",
        body_style
    ))

    table_data = [
        ['Outcome', 'Treatment', 'Control', 'p-value'],
        ['Primary', '78.3±12.4', '65.2±14.1', '<0.001'],
        ['Secondary A', '45.6±8.9', '42.1±9.2', '0.032'],
        ['Secondary B', '92.1±5.4', '88.7±6.1', '0.008'],
    ]
    table = Table(table_data, colWidths=[1.5*inch, 1.2*inch, 1.2*inch, 1*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    story.append(table)
    story.append(PageBreak())

    # Ambiguous: "Summary" at end should map to conclusion, NOT "Summary Statistics" in results
    story.append(Paragraph("VI. SUMMARY", heading_style))
    story.append(Paragraph(
        "In summary, this study demonstrates the effectiveness of our proposed approach for cardiac "
        "signal processing. The key contributions include improved detection accuracy and reduced "
        "computational requirements. Future work should explore application to real-time monitoring "
        "systems and validation in clinical populations.",
        body_style
    ))
    story.append(Paragraph(
        "The implications of these findings extend beyond the immediate application domain and "
        "suggest broader utility in biomedical signal processing applications.",
        body_style
    ))

    # References at end
    story.append(PageBreak())
    story.append(Paragraph("REFERENCES", heading_style))
    for i in range(1, 15):
        story.append(Paragraph(
            f"[{i}] A. Author and B. Coauthor, \"Title of referenced paper {i},\" "
            f"Journal Name, vol. {10+i}, pp. {i*10}-{i*10+8}, 20{10+i}.",
            body_style
        ))

    doc.build(story)
    print(f"Created: {FIXTURES_DIR / 'sample_ambiguous_sections.pdf'}")


def create_complex_tables():
    """
    PDF 3: Tables with Challenges (sample_complex_tables.pdf)

    12+ pages with various table scenarios:
    - Forward references
    - Split tables (simulated with continuation note)
    - Tables without captions
    - Multi-line captions
    - Nested structures
    """
    doc = SimpleDocTemplate(
        str(FIXTURES_DIR / "sample_complex_tables.pdf"),
        pagesize=letter,
        rightMargin=inch,
        leftMargin=inch,
        topMargin=inch,
        bottomMargin=inch
    )

    styles = getSampleStyleSheet()
    heading_style = ParagraphStyle(
        'Heading1',
        parent=styles['Heading1'],
        fontSize=14,
        spaceBefore=18,
        spaceAfter=6
    )
    body_style = ParagraphStyle(
        'Body',
        parent=styles['Normal'],
        fontSize=11,
        alignment=TA_JUSTIFY,
        spaceAfter=12
    )

    story = []

    # Title
    story.append(Paragraph(
        "Complex Table Structures in Academic Documents",
        ParagraphStyle('Title', parent=styles['Title'], fontSize=16, alignment=TA_CENTER)
    ))
    story.append(Spacer(1, 0.5*inch))

    # Page 1-2: Introduction with forward reference
    story.append(Paragraph("1. Introduction", heading_style))
    story.append(Paragraph(
        "This document demonstrates various table structures commonly found in academic papers. "
        "As shown in Table 2 (see page 5), the results support our hypothesis. We will first "
        "discuss the methodology before presenting the complete data in subsequent tables.",
        body_style
    ))
    story.append(Paragraph(
        "The forward reference to Table 2 above is intentional - readers often encounter such "
        "references before seeing the actual table. Our extraction system should handle this.",
        body_style
    ))
    story.append(PageBreak())

    # Page 3: Methods
    story.append(Paragraph("2. Methods", heading_style))
    story.append(Paragraph(
        "Data were collected from 100 participants across three experimental conditions. "
        "Measurements were taken at baseline, 30 minutes, and 60 minutes post-intervention.",
        body_style
    ))
    story.append(PageBreak())

    # Page 4: Table 1 with caption above
    story.append(Paragraph("3. Results", heading_style))
    story.append(Paragraph("<b>Table 1:</b> Baseline characteristics of study participants", body_style))

    table1_data = [
        ['Variable', 'Group A (n=50)', 'Group B (n=50)', 'p-value'],
        ['Age (years)', '42.3 ± 11.2', '41.8 ± 10.9', '0.82'],
        ['Sex (M/F)', '26/24', '28/22', '0.69'],
        ['BMI (kg/m²)', '25.4 ± 3.8', '26.1 ± 4.2', '0.38'],
        ['Baseline HR (bpm)', '72.1 ± 10.5', '71.4 ± 11.2', '0.74'],
        ['SBP (mmHg)', '122 ± 14', '124 ± 15', '0.48'],
        ['DBP (mmHg)', '78 ± 9', '79 ± 10', '0.59'],
    ]
    table1 = Table(table1_data, colWidths=[1.5*inch, 1.4*inch, 1.4*inch, 1*inch])
    table1.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    story.append(table1)
    story.append(Spacer(1, 0.25*inch))
    story.append(Paragraph(
        "Table 1 shows that the groups were well-matched at baseline with no significant "
        "differences in demographic or physiological variables.",
        body_style
    ))
    story.append(PageBreak())

    # Page 5: Table 2 (referenced earlier on page 1)
    story.append(Paragraph(
        "<b>Table 2:</b> Primary and secondary outcomes at 60 minutes post-intervention. "
        "Values represent mean change from baseline ± standard deviation. Statistical significance "
        "determined by independent samples t-test with Bonferroni correction.",
        body_style
    ))

    table2_data = [
        ['Outcome', 'Group A', 'Group B', 'Difference', '95% CI', 'p-value'],
        ['Primary', '-8.4 ± 5.2', '-3.1 ± 4.8', '-5.3', '[-7.1, -3.5]', '<0.001'],
        ['Secondary 1', '-12.3 ± 8.1', '-7.8 ± 7.4', '-4.5', '[-7.6, -1.4]', '0.005'],
        ['Secondary 2', '+2.1 ± 3.4', '+1.2 ± 3.1', '+0.9', '[-0.3, 2.1]', '0.14'],
        ['Secondary 3', '-6.7 ± 4.9', '-5.2 ± 5.3', '-1.5', '[-3.5, 0.5]', '0.14'],
    ]
    table2 = Table(table2_data, colWidths=[1.1*inch, 1*inch, 1*inch, 0.9*inch, 1.1*inch, 0.7*inch])
    table2.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    story.append(table2)
    story.append(PageBreak())

    # Pages 6-7: Large table split across pages (simulated)
    story.append(Paragraph(
        "<b>Table 3:</b> Complete longitudinal data for all participants (continued on next page)",
        body_style
    ))

    # First part of table
    table3a_data = [['ID', 'Baseline', '15 min', '30 min', '45 min', '60 min']]
    for i in range(1, 26):
        table3a_data.append([
            f'P{i:03d}',
            f'{70+i*0.5:.1f}',
            f'{68+i*0.4:.1f}',
            f'{66+i*0.3:.1f}',
            f'{65+i*0.2:.1f}',
            f'{64+i*0.1:.1f}'
        ])
    table3a = Table(table3a_data, colWidths=[0.8*inch, 0.9*inch, 0.9*inch, 0.9*inch, 0.9*inch, 0.9*inch])
    table3a.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
    ]))
    story.append(table3a)
    story.append(PageBreak())

    # Continuation
    story.append(Paragraph("<b>Table 3 (continued)</b>", body_style))
    table3b_data = [['ID', 'Baseline', '15 min', '30 min', '45 min', '60 min']]
    for i in range(26, 51):
        table3b_data.append([
            f'P{i:03d}',
            f'{70+i*0.5:.1f}',
            f'{68+i*0.4:.1f}',
            f'{66+i*0.3:.1f}',
            f'{65+i*0.2:.1f}',
            f'{64+i*0.1:.1f}'
        ])
    table3b = Table(table3b_data, colWidths=[0.8*inch, 0.9*inch, 0.9*inch, 0.9*inch, 0.9*inch, 0.9*inch])
    table3b.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
    ]))
    story.append(table3b)
    story.append(PageBreak())

    # Page 8: Table without caption (referenced as "the table below")
    story.append(Paragraph("4. Subgroup Analysis", heading_style))
    story.append(Paragraph(
        "Analysis of the age subgroups revealed interesting patterns. The table below shows "
        "the response rates stratified by age category. Younger participants showed larger "
        "treatment effects overall.",
        body_style
    ))

    table4_data = [
        ['Age Group', 'N', 'Response Rate', 'Effect Size'],
        ['18-29', '32', '78%', '0.82'],
        ['30-44', '41', '68%', '0.65'],
        ['45-59', '27', '52%', '0.41'],
    ]
    table4 = Table(table4_data, colWidths=[1.2*inch, 0.8*inch, 1.2*inch, 1.2*inch])
    table4.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    story.append(table4)
    story.append(PageBreak())

    # Page 9: Table with multi-line caption including footnote
    caption_text = (
        "<b>Table 4:</b> Adverse events reported during the study period. Values represent "
        "number of events (percentage of participants). Serious adverse events (SAEs) are marked "
        "with asterisk (*). All SAEs were reviewed by the Data Safety Monitoring Board and "
        "determined to be unrelated to study intervention."
    )
    story.append(Paragraph(caption_text, body_style))

    table5_data = [
        ['Event', 'Group A', 'Group B', 'Total'],
        ['Headache', '8 (16%)', '6 (12%)', '14 (14%)'],
        ['Nausea', '4 (8%)', '5 (10%)', '9 (9%)'],
        ['Fatigue', '6 (12%)', '7 (14%)', '13 (13%)'],
        ['Dizziness', '3 (6%)', '2 (4%)', '5 (5%)'],
        ['Hospitalization*', '1 (2%)', '0 (0%)', '1 (1%)'],
    ]
    table5 = Table(table5_data, colWidths=[1.5*inch, 1.2*inch, 1.2*inch, 1.2*inch])
    table5.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    story.append(table5)
    story.append(PageBreak())

    # Page 10: Nested/hierarchical table structure
    story.append(Paragraph("5. Correlation Analysis", heading_style))
    story.append(Paragraph(
        "<b>Table 5:</b> Correlation matrix showing relationships between outcome measures",
        body_style
    ))

    table6_data = [
        ['', 'Primary', 'Sec. 1', 'Sec. 2', 'Sec. 3'],
        ['Primary', '1.00', '', '', ''],
        ['Secondary 1', '0.72***', '1.00', '', ''],
        ['Secondary 2', '0.45**', '0.38*', '1.00', ''],
        ['Secondary 3', '0.68***', '0.61***', '0.52**', '1.00'],
    ]
    table6 = Table(table6_data, colWidths=[1.2*inch, 1*inch, 1*inch, 1*inch, 1*inch])
    table6.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    story.append(table6)
    story.append(Paragraph(
        "* p < 0.05, ** p < 0.01, *** p < 0.001",
        ParagraphStyle('Footnote', parent=styles['Normal'], fontSize=9)
    ))

    # Conclusion
    story.append(PageBreak())
    story.append(Paragraph("6. Conclusions", heading_style))
    story.append(Paragraph(
        "This document has demonstrated various table structures that may be encountered in "
        "academic publications. Proper extraction and indexing of these tables is essential "
        "for comprehensive literature search capabilities.",
        body_style
    ))

    doc.build(story)
    print(f"Created: {FIXTURES_DIR / 'sample_complex_tables.pdf'}")


def create_edge_cases():
    """
    PDF 5: Edge Cases (sample_edge_cases.pdf)

    8 pages with special characters and formatting:
    - Greek letters
    - Mathematical notation
    - Unicode quotation marks
    - Superscript/subscript
    - URLs and DOIs
    """
    doc = SimpleDocTemplate(
        str(FIXTURES_DIR / "sample_edge_cases.pdf"),
        pagesize=letter,
        rightMargin=inch,
        leftMargin=inch,
        topMargin=inch,
        bottomMargin=inch
    )

    styles = getSampleStyleSheet()
    heading_style = ParagraphStyle(
        'Heading1',
        parent=styles['Heading1'],
        fontSize=14,
        spaceBefore=18,
        spaceAfter=6
    )
    body_style = ParagraphStyle(
        'Body',
        parent=styles['Normal'],
        fontSize=11,
        alignment=TA_JUSTIFY,
        spaceAfter=12
    )

    story = []

    # Title
    story.append(Paragraph(
        "Edge Cases in Text Extraction: Greek Letters, Mathematics, and Unicode",
        ParagraphStyle('Title', parent=styles['Title'], fontSize=16, alignment=TA_CENTER)
    ))
    story.append(Spacer(1, 0.5*inch))

    # Abstract with Greek letters
    story.append(Paragraph("Abstract", heading_style))
    # Note: Greek letters may render as entities depending on font
    story.append(Paragraph(
        "This paper examines the extraction of special characters from PDF documents. "
        "We analyze the transfer coefficients alpha and beta across multiple experimental "
        "conditions. The gamma distribution parameter was estimated at 2.34 with confidence "
        "interval delta of 0.12. Statistical significance was determined using chi-squared "
        "test with threshold of 0.05.",
        body_style
    ))
    story.append(PageBreak())

    # Mathematical content
    story.append(Paragraph("1. Mathematical Notation", heading_style))
    story.append(Paragraph(
        "The primary equation governing the system dynamics is given by:",
        body_style
    ))
    story.append(Paragraph(
        "dV/dt = -V/RC + I<sub>in</sub>/C",
        ParagraphStyle('Equation', parent=styles['Normal'], fontSize=12, alignment=TA_CENTER, spaceAfter=12)
    ))
    story.append(Paragraph(
        "where V represents voltage, R is resistance (measured in Ohms), C is capacitance "
        "(measured in Farads), and I<sub>in</sub> is the input current. The time constant "
        "tau = RC determines the system response speed.",
        body_style
    ))
    story.append(Paragraph(
        "For the frequency domain analysis, we apply the Fourier transform:",
        body_style
    ))
    story.append(Paragraph(
        "H(f) = 1 / (1 + j2*pi*f*RC)",
        ParagraphStyle('Equation', parent=styles['Normal'], fontSize=12, alignment=TA_CENTER, spaceAfter=12)
    ))
    story.append(PageBreak())

    # Superscript and subscript
    story.append(Paragraph("2. Subscripts and Superscripts", heading_style))
    story.append(Paragraph(
        "Concentrations were measured for Na<sup>+</sup>, K<sup>+</sup>, Ca<sup>2+</sup>, "
        "and Cl<sup>-</sup> ions. The Nernst potential E<sub>Na</sub> was calculated using "
        "standard physiological values. Membrane potential V<sub>m</sub> ranged from -90mV "
        "to +40mV during the action potential.",
        body_style
    ))
    story.append(Paragraph(
        "The reaction rate k<sub>1</sub> was measured at 25°C and k<sub>2</sub> at 37°C. "
        "Results showed a Q<sub>10</sub> value of 2.3, indicating temperature sensitivity.",
        body_style
    ))
    story.append(PageBreak())

    # Unicode quotation marks and special punctuation
    story.append(Paragraph("3. Quotations and Special Characters", heading_style))
    # Using HTML entities for smart quotes since reportlab may not handle them directly
    story.append(Paragraph(
        'According to Smith (2020), "the relationship between heart rate and blood pressure '
        'is complex and multifactorial." This finding contradicts earlier work suggesting '
        '"a simple linear relationship" (Jones, 2015).',
        body_style
    ))
    story.append(Paragraph(
        "The em-dash is used for parenthetical statements - like this one - while the "
        "en-dash indicates ranges (e.g., pages 10-15, years 2010-2020).",
        body_style
    ))
    story.append(PageBreak())

    # Table with special characters
    story.append(Paragraph("4. Data with Special Characters", heading_style))
    story.append(Paragraph("<b>Table 1:</b> Ion concentrations and potentials", body_style))

    table_data = [
        ['Ion', 'Intracellular (mM)', 'Extracellular (mM)', 'E (mV)'],
        ['Na+', '12', '145', '+67'],
        ['K+', '155', '4', '-98'],
        ['Ca2+', '0.0001', '1.8', '+129'],
        ['Cl-', '4', '120', '-89'],
    ]
    table = Table(table_data, colWidths=[1.2*inch, 1.4*inch, 1.4*inch, 1*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    story.append(table)
    story.append(PageBreak())

    # URLs and DOIs
    story.append(Paragraph("5. References with URLs and DOIs", heading_style))
    story.append(Paragraph(
        "Digital Object Identifiers (DOIs) provide persistent links to scholarly content. "
        "For example, the foundational HRV guidelines can be found at:",
        body_style
    ))
    story.append(Paragraph(
        "https://doi.org/10.1161/01.CIR.93.5.1043",
        ParagraphStyle('URL', parent=styles['Normal'], fontSize=10, leftIndent=36)
    ))
    story.append(Paragraph(
        "Additional resources are available at the project repository:",
        body_style
    ))
    story.append(Paragraph(
        "https://github.com/example/cardiac-analysis",
        ParagraphStyle('URL', parent=styles['Normal'], fontSize=10, leftIndent=36)
    ))
    story.append(PageBreak())

    # Hyphenated words at line breaks (simulated)
    story.append(Paragraph("6. Text Flow and Hyphenation", heading_style))
    story.append(Paragraph(
        "The electro-physiological characteristics of the sino-atrial node determine "
        "the intrinsic heart rate. Anti-arrhythmic medications target specific ion "
        "channels to restore normal cardiac rhythm. The sympatho-vagal balance is "
        "assessed through frequency-domain analysis of heart rate variability.",
        body_style
    ))
    story.append(Paragraph(
        "Long technical terms like electrocardiography, magnetoencephalography, and "
        "photoplethysmography may be hyphenated at line breaks in some documents, "
        "creating extraction challenges.",
        body_style
    ))

    # Conclusions
    story.append(PageBreak())
    story.append(Paragraph("7. Conclusions", heading_style))
    story.append(Paragraph(
        "Text extraction from PDF documents must handle a variety of special characters "
        "and formatting conventions. This includes Greek letters (commonly used in "
        "scientific notation), subscripts and superscripts (essential for chemical "
        "formulas and mathematical expressions), and various Unicode characters that "
        "may appear in quotations or specialized terminology.",
        body_style
    ))

    doc.build(story)
    print(f"Created: {FIXTURES_DIR / 'sample_edge_cases.pdf'}")


def create_mixed_ocr():
    """
    PDF 4: Mixed OCR/Text (sample_mixed_ocr.pdf)

    6 pages with alternating native text and image-only pages:
    - Page 1: Normal text (Introduction)
    - Page 2: Scanned image (Methods - embedded as image)
    - Page 3: Normal text (Results)
    - Page 4: Scanned figure with caption as image
    - Page 5: Normal text (Discussion)
    - Page 6: Two-column layout as image

    Uses PyMuPDF directly to embed rasterized text as images.
    """
    import pymupdf

    doc = pymupdf.open()

    # Page 1: Normal text (Introduction)
    page1 = doc.new_page()
    page1.insert_text(
        (72, 72),
        "1. Introduction\n\n"
        "This document tests OCR fallback functionality. "
        "It contains a mix of pages with native text extraction "
        "and pages that require optical character recognition. "
        "The system should automatically detect which pages need OCR "
        "and apply it selectively.\n\n"
        "Lorem ipsum dolor sit amet, consectetur adipiscing elit. "
        "Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.",
        fontsize=11
    )

    # Page 2: Create text, render to image, insert as image-only
    temp_doc = pymupdf.open()
    temp_page = temp_doc.new_page()
    temp_page.insert_text(
        (72, 72),
        "2. Methods\n\n"
        "This page contains the methods section. "
        "It has been converted to an image to simulate a scanned document. "
        "OCR should be able to extract this text.\n\n"
        "The experimental procedure involved multiple steps including "
        "data collection, preprocessing, and statistical analysis.",
        fontsize=11
    )
    pix = temp_page.get_pixmap(dpi=150)
    temp_doc.close()

    page2 = doc.new_page()
    page2.insert_image(page2.rect, pixmap=pix)

    # Page 3: Normal text (Results)
    page3 = doc.new_page()
    page3.insert_text(
        (72, 72),
        "3. Results\n\n"
        "The results of our analysis are presented below. "
        "This page uses native text extraction and does not require OCR. "
        "Statistical significance was achieved (p < 0.05).\n\n"
        "Table 1 shows the primary outcomes of the study. "
        "The intervention group showed significant improvement.",
        fontsize=11
    )

    # Page 4: Figure with caption as image
    temp_doc = pymupdf.open()
    temp_page = temp_doc.new_page()
    temp_page.draw_rect(pymupdf.Rect(100, 150, 500, 400))
    temp_page.insert_text((100, 420), "Figure 1: Experimental results showing treatment effect", fontsize=10)
    temp_page.insert_text(
        (72, 72),
        "This page contains a figure that has been scanned.",
        fontsize=11
    )
    pix = temp_page.get_pixmap(dpi=150)
    temp_doc.close()

    page4 = doc.new_page()
    page4.insert_image(page4.rect, pixmap=pix)

    # Page 5: Normal text (Discussion)
    page5 = doc.new_page()
    page5.insert_text(
        (72, 72),
        "4. Discussion\n\n"
        "Our findings demonstrate the effectiveness of the approach. "
        "This page contains native text that should be extracted directly. "
        "The implications of these results are significant.\n\n"
        "Future work should investigate the generalizability of these "
        "findings to broader populations and clinical settings.",
        fontsize=11
    )

    # Page 6: Two-column layout as image
    temp_doc = pymupdf.open()
    temp_page = temp_doc.new_page()
    temp_page.insert_text(
        (50, 72),
        "Left Column\n\n"
        "This is the left column\n"
        "of a two-column layout.\n"
        "Text continues here with\n"
        "multiple lines of content.\n"
        "The extraction should\n"
        "handle this layout.",
        fontsize=10
    )
    temp_page.insert_text(
        (320, 72),
        "Right Column\n\n"
        "This is the right column\n"
        "of the same layout.\n"
        "Reading order may vary\n"
        "depending on extraction.\n"
        "Both columns should be\n"
        "extracted properly.",
        fontsize=10
    )
    pix = temp_page.get_pixmap(dpi=150)
    temp_doc.close()

    page6 = doc.new_page()
    page6.insert_image(page6.rect, pixmap=pix)

    output = FIXTURES_DIR / "sample_mixed_ocr.pdf"
    doc.save(output)
    doc.close()
    print(f"Created: {output}")


def main():
    """Generate all stress test PDFs."""
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

    print("Generating stress test PDFs...")
    create_academic_full()
    create_ambiguous_sections()
    create_complex_tables()
    create_edge_cases()
    create_mixed_ocr()
    print("\nAll stress test PDFs created successfully!")
    print(f"Location: {FIXTURES_DIR}")


if __name__ == "__main__":
    main()

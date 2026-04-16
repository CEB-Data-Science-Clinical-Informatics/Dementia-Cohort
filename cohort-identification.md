# Dementia Cohort Identification

- **Author:** Htun Teza
- **Date:** 10 April 2026

> [!IMPORTANT]
> Please be aware that the information provided here is current as of the date of this documentation. However, it is subject to potential changes or updates in the future.

## Contents

- [Data Source](#data-source)
- [Cohort Identification](#cohort-identification)
    - [Diagnosis of Dementia](#diagnosis-of-dementia)
    - [Prescription of Anti-Dementia Medications](#prescription-of-anti-dementia-medications)
    - [Merging](#merging)
- [Subtype Classification](#subtype-classification)
    - [Dementia Subtypes](#dementia-subtypes)
    - [Initial Label](#initial-label)
    - [Final Label](#final-label)
    - [Data Format](#data-format)
- [Final Cohort](#final-cohort)
- [Subtype Distribution](#subtype-distribution)
- [Subtype Transitions](#subtype-transitions)

---

## Data Source

This cohort was retrieved from the Ramathibodi Hospital Information System covering **1 January 2010 to 31 December 2025**, processed as of 16 March 2026. The data warehouse was developed by the Data Science and Clinical Informatics Division, Department of Clinical Epidemiology and Biostatistics, Faculty of Medicine Ramathibodi Hospital, Mahidol University.

---

## Cohort Identification

Patients were identified using two parallel criteria applied with an **OR condition** — meeting either criterion was sufficient for inclusion.

### Diagnosis of Dementia

Patients were identified from clinic and in-patient visit records using ICD-10-TM diagnostic codes. The following codes and their subcodes were used:

ICD-10-TM Code | Dementia Subtype
-|-
F000, F001, F002, F009 | Alzheimer's Disease
G300, G301, G308, G309 | Alzheimer's Disease
F010, F011, F012, F013, F018, F019 | Vascular Dementia
G3183 | Dementia with Lewy Bodies
F020, G310 | Frontotemporal Dementia
G232, G233 | Multiple System Atrophy
F023 | Parkinson's Disease Dementia
G231 | Progressive Supranuclear Palsy

### Prescription of Anti-Dementia Medications

Patients prescribed any of the following anti-dementia medications were included, regardless of whether a formal dementia diagnosis was recorded. These medications are used as a proxy for **Unspecified Dementia** — cases where clinical management is consistent with dementia but a specific ICD-10 subtype has not been documented.

Medication | Drug Class
-|-
Donepezil | Acetylcholinesterase inhibitor
Rivastigmine Base | Acetylcholinesterase inhibitor
Rivastigmine Tartrate | Acetylcholinesterase inhibitor
Galantamine | Acetylcholinesterase inhibitor
Memantine HCl | NMDA receptor antagonist

Unlike the HT cohort, no further exclusion logic is applied to medication-only patients. Anti-dementia medications have sufficiently specific indications that their prescription is treated as evidence of dementia management without requiring a differential exclusion step.

### Merging

Combining both criteria categorises patients into three groups:

1. Patients with ICD-10 dementia codes only (*n* = 3,127)
2. Patients with both ICD-10 codes and anti-dementia medication prescriptions (*n* = 5,614)
3. Patients with anti-dementia medication prescriptions only (*n* = 4,658)

All three groups are included in the cohort, yielding a total of **13,399 dementia subjects**.

The **index date** is defined as the earliest date on which a patient met either criterion — the first dementia-related diagnosis date or the first anti-dementia medication prescription date, whichever came first.

---

## Subtype Classification

Each patient is assigned two subtype labels: an **initial label** based on information available at the index date, and a **final label** based on the patient's complete longitudinal record.

### Dementia Subtypes

Subtypes | Classification Basis
-|-
Alzheimer's Disease (AD) | ICD-10 codes: F000, F001, F002, F009, G300, G301, G308, G309
Vascular Dementia (VaD) | ICD-10 codes: F010, F011, F012, F013, F018, F019
Unspecified Dementia | Prescription of anti-dementia medication without any specific subtype ICD-10 code
Other Dementia | ICD-10 codes: G3183 (Lewy Bodies), F020/G310 (Frontotemporal), G232/G233 (MSA), F023 (PD Dementia), G231 (PSP)
Mixed Dementia | Coexistence of two or more dementia subtype pathologies recorded in the same individual

### Initial Label

The initial label is assigned at the **index date** using only the information present at that point in time.

- **Diagnosis only** → subtype is derived directly from the ICD-10 code(s) present at index
- **Medication only** → labelled as Unspecified Dementia
- **Both diagnosis and medication** → subtype is derived from the ICD-10 code(s); medication confirms the clinical picture but does not change the subtype assignment

If multiple subtype-specific ICD-10 codes from different subtypes are present at the index date, the patient is labelled **Mixed Dementia** at initial assignment.

### Final Label

The final label is assigned after reviewing the patient's **complete longitudinal record** at Ramathibodi Hospital. This allows subtype refinement over time — most notably, patients initially labelled Unspecified (medication-only at index) may later accrue a specific ICD-10 diagnosis, resolving them into AD, VaD, Other, or Mixed.

The final label follows the same logic as the initial label but applied across the full observation window:

- A patient who accumulates ICD-10 codes from more than one subtype at any point → **Mixed Dementia**
- A medication-only patient who never receives a specific ICD-10 code → remains **Unspecified Dementia**
- A medication-only patient who later receives a specific ICD-10 code → reclassified to that subtype (or Mixed if multiple)

### Data Format

The table below illustrates how the labeling logic applies to representative patients. Raw diagnosis and medication codes are shown in Slide 4; collapsed dates (earliest per domain) in Slide 5; and final label assignments in Slide 6.

HN | Index Date | Diagnosis Date | Medication Date | AD Date | VaD Date | Other Date | Initial Label | Final Label
-|-|-|-|-|-|-|-|-
A | 2022-10-17 | 2022-10-17 | — | — | — | 2022-10-17 | Diagnosis / Other | Diagnosis / Other
B | 2010-03-06 | 2012-09-01 | 2010-03-06 | — | 2012-09-01 | — | Medication / Unspecified | Both / VaD
C | 2023-02-02 | — | 2023-02-02 | — | — | — | Medication / Unspecified | Medication / Unspecified
D | 2016-08-24 | 2016-08-24 | 2016-08-24 | 2016-08-24 | — | — | Both / AD | Both / AD
E | 2012-09-12 | 2012-09-12 | — | 2012-09-12 | — | 2014-06-07 | Diagnosis / AD | Diagnosis / Mixed

**Notes:**
- Patient B was identified first by medication (2010); a VaD diagnosis came later (2012) → initial label is Unspecified, final label resolves to VaD.
- Patient E had an AD diagnosis at index (2012) and later accrued an Other subtype diagnosis (2014) → final label becomes Mixed.
- Patient C remained medication-only throughout → Unspecified at both time points.

---

## Final Cohort

All patients meeting either inclusion criterion are included in the **CEB Data Warehouse – Dementia Theme**. Only adult patients aged **18 years or older** on the index date are included. The cohort covers the period from **1 January 2010 to 31 December 2025**.

---

## Subtype Distribution

The table below shows the number of patients (*n*) and percentage (%) by subtype at index date and at final observation.

Subtype | Index *n* (%) | Final *n* (%)
-|-|-
Alzheimer's Disease | 3,570 (26.6) | 5,047 (37.7)
Vascular Dementia | 1,158 (8.6) | 1,337 (10.0)
Unspecified (Medication) | 8,148 (60.8) | 4,658 (34.8)
Other Dementia | 394 (3.0) | 421 (3.1)
Mixed Dementia | 129 (1.0) | 1,936 (14.4)
**Total** | **13,399 (100.0)** | **13,399 (100.0)**

The large shift from Unspecified at index to specific subtypes at final reflects longitudinal accrual of ICD-10 diagnoses among patients initially identified by medication only. Mixed Dementia increases substantially (1.0% → 14.4%), driven primarily by Unspecified patients who eventually receive multiple subtype-specific codes.

---

## Subtype Transitions

The table below shows how initial subtype labels transition to final subtype labels. Rows are index subtypes; columns are final subtypes. Values are *n* (%).

| Index \ Final | AD | VaD | Unspecified | Mixed | Others | **Row Total** |
|-|-|-|-|-|-|-|
| AD | 3,044 (85.3) | — | — | 526 (14.7) | — | **3,570 (26.6)** |
| VaD | — | 867 (74.9) | — | 291 (25.1) | — | **1,158 (8.6)** |
| Unspecified | 2,003 (24.6) | 470 (5.8) | 4,658 (57.2) | 923 (11.3) | 94 (1.2) | **8,148 (60.8)** |
| Mixed | — | — | — | 129 (100.0) | — | **129 (1.0)** |
| Others | 67 (17.0) | — | — | — | 327 (83.0) | **394 (3.0)** |
| **Column Total** | **5,047 (37.7)** | **1,337 (10.0)** | **4,658 (34.8)** | **1,936 (14.4)** | **421 (3.1)** | **13,399** |

**Key observations:**
- AD and VaD labels are relatively stable: 85.3% of index-AD and 74.9% of index-VaD retain their subtype at final.
- The largest absolute transition is Unspecified → AD (*n* = 2,003), reflecting delayed ICD documentation in medication-first patients.
- 14.7% of index-AD and 25.1% of index-VaD patients accumulate an additional subtype pathology, resolving to Mixed at final.
- Once labelled Mixed at index, patients remain Mixed (100%).
- 83.0% of Other Dementia patients retain their subtype; 17.0% transition to AD, likely reflecting co-occurring Alzheimer's pathology.
# Dementia Cohort Identification

- **Author:** Htun Teza
- **Date:** 8 May 2026

> [!IMPORTANT]
> Please be aware that the information provided here is current as of the date of this documentation. However, it is subject to potential changes or updates in the future.

## Contents
- [Dementia Cohort Identification](#dementia-cohort-identification)
  - [Contents](#contents)
  - [Data Source](#data-source)
  - [Loosely Defined Criteria](#loosely-defined-criteria)
  - [Exactly Defined Criteria](#exactly-defined-criteria)
  - [Codes Under Review](#codes-under-review)
  - [Subtype Classification](#subtype-classification)
  - [Final Cohort](#final-cohort)
  - [Subtype Distribution](#subtype-distribution)

---

## Data Source

This cohort was retrieved from the Ramathibodi Hospital Information System covering **1 January 2010 to 31 December 2025**, processed as of 16 March 2026. The data warehouse was developed by the Data Science and Clinical Informatics Division, Department of Clinical Epidemiology and Biostatistics, Faculty of Medicine Ramathibodi Hospital, Mahidol University.

---

## Loosely Defined Criteria

Patients were identified using two parallel criteria applied with an **OR condition** — meeting either criterion was sufficient for inclusion.

### Diagnosis of Dementia

Patients were identified from clinic and in-patient visit records using ICD-10-TM diagnostic codes. The following codes were used:

| ICD-10-TM Code | Dementia Subtype | Label |
|:---|:---|:---|
| F000, F001, F002, F009 | Alzheimer's Disease | AD |
| G300, G301, G308, G309 | Alzheimer's Disease | AD |
| F010, F011, F012, F013, F018, F019 | Vascular Dementia | VaD |
| G318 | Other Specified Degenerative Dementia | Other |
| F020, G310 | Frontotemporal Dementia | Other |
| F023 | Parkinson's Disease Dementia | Other |
| G232, G233 | Multiple System Atrophy | Other |
| G231 | Progressive Supranuclear Palsy | Other |
| F021, F022, F024, F028 | Other Dementia (CJD, Huntington's, HIV, other) | Other |
| F03 | Unspecified Dementia | Unspecified |

> [!NOTE]
> Dementia with Lewy Bodies (DLB) does not have a dedicated ICD-10-TM code. In clinical practice at Ramathibodi Hospital, DLB cases are coded under **G318** (Other Specified Degenerative Diseases of the Nervous System), which is a broader category not exclusive to DLB. As a result, G318 cannot be reliably mapped to DLB as a distinct subtype and is therefore classified under **Other Dementia** in this cohort.

### Prescription of Anti-Dementia Medications

Patients prescribed any of the following anti-dementia medications were included, regardless of whether a formal dementia diagnosis was recorded.

| Medication | Drug Class |
|:---|:---|
| Donepezil | Acetylcholinesterase inhibitor |
| Rivastigmine | Acetylcholinesterase inhibitor |
| Galantamine | Acetylcholinesterase inhibitor |
| Memantine HCl | NMDA receptor antagonist |

> [!IMPORTANT]
> This criterion identifies patients by prescription only, with no exclusion rules applied at this stage. Exclusion rules are applied in the [Exactly Defined Criteria](#exactly-defined-criteria) section, where the remaining medication-only patients are labelled as **Unspecified (Inferred)** and merged with **Unspecified (Diagnosed)** patients (F03) into a single **Unspecified** subtype at final label assignment.

### Merging for Tentative Cohort

Utilizing these dual inclusion criteria — diagnosis codes and medication prescriptions — allowed us to categorize patients into three distinct groups based on their dementia status:

1. Patients with ICD-10 dementia codes only (*n* = —)
2. Patients with both ICD-10 dementia codes and anti-dementia medication prescriptions (*n* = —)
3. Patients with anti-dementia medication prescriptions only (*n* = —)

Groups 1 and 2 are considered to have a confirmed diagnosis of dementia. Group 3 undergoes further review under the [Exactly Defined Criteria](#exactly-defined-criteria) to determine eligibility for inclusion as **Unspecified (Inferred)** dementia. The index date for all groups is determined after exclusion rules are applied.

---

## Exactly Defined Criteria

### Inferred Diagnosis of Dementia

Patients prescribed anti-dementia medications without a corresponding ICD-10 dementia diagnosis require further review before a dementia diagnosis can be inferred. The medication arm is split into two groups — **AChEI** (Donepezil, Rivastigmine, Galantamine) and **Memantine** — which are assessed separately against their respective exclusion criteria. Patients may appear in both groups if prescribed both drug classes. After exclusions, the remaining patients from both groups are merged into the **Unspecified (Inferred)** dementia group.

#### AChEI Group

Patients with any AChEI prescription are excluded from the dementia cohort if an **MCI diagnosis exists anywhere in their medical history**, as AChEI is also indicated for MCI. The reasonable inferred diagnosis for such patients is MCI rather than dementia.

| Exclusion Rule | Criterion |
|:---|:---|
| MCI differential | MCI diagnosis (F067, R41, R418) present anywhere in patient's medical history |

#### Memantine Group

Patients with any Memantine prescription are assessed against two exclusion criteria, as Memantine has indications beyond dementia.

| Exclusion Rule | Criterion |
|:---|:---|
| Schizophrenia differential | Clozapine prescription **or** schizophrenia-related diagnosis present anywhere in patient's medical history |
| Radiotherapy differential | Memantine prescription falls within the course of radiotherapy (between first and last recorded radiotherapy date) |

##### Radiotherapy

###### Method 1 — ICD-9-CM Procedure Codes

The course of radiotherapy is identified using the following ICD-9-CM procedure codes:

| ICD-9-CM Code | Description |
|:---|:---|
| 9221 | Superficial radiation |
| 9222 | Orthovoltage radiation |
| 9223 | Radioisotope teleradiotherapy |
| 9224 | Teleradiotherapy using photons |
| 9225 | Teleradiotherapy using electrons |
| 9226 | Teleradiotherapy using other particles |
| 9227 | Implantation or insertion of radioactive elements |
| 9229 | Other radiotherapy |
| 9230 | Stereotactic radiosurgery, NOS |
| 9231 | Single source photon radiosurgery |
| 9232 | Multi-source photon radiosurgery (Gamma Knife) |
| 9233 | Particulate radiosurgery |
| 9239 | Stereotactic radiosurgery, NEC |
| 9241 | Intraoperative electron radiation therapy |

> [!NOTE]
> At this stage, any Memantine prescription recorded during a course of radiotherapy — regardless of the body site irradiated — is excluded from consideration as a dementia indicator. Refinement of this criterion to restrict exclusion to **brain** radiotherapy specifically (by combining radiotherapy procedure codes with co-occurring brain tumour or brain metastasis diagnosis codes) is deferred to a subsequent meeting.

###### Method 2 (Alternative) — Billing Codes Specific to Institution

The following billing codes are specific to Ramathibodi Hospital. Each participating institution is expected to identify and confirm their equivalent billing codes for radiotherapy delivery.

| Billing Code | Procedure Name | Translation |
|:---|:---|:---|
| X00568 | การฉายรังสีด้วยเครื่อง Co-60 | Co-60 radiotherapy |
| X00569 | การฉายแสงด้วยเครื่องเร่งอนุภาค | Linear accelerator radiotherapy |
| X00572 | การใส่แร่อิริเดียม (Insertion) | Iridium brachytherapy insertion |
| X00576 | การฝังแร่อิริเดียม (Implantation) first loading | Iridium brachytherapy implantation — first loading |
| X00577 | การฝังแร่อิริเดียม (Implantation) next loading | Iridium brachytherapy implantation — subsequent loading |
| X00579 | การฉายแสงทั้งตัว (Total Body Irradiation) | Total body irradiation |
| X00825 | ค่าฉายรังสี Stereotactic Radiosurgery or Stereotactic Radiotherapy (Brain/Spine) | Stereotactic radiosurgery/radiotherapy — Brain/Spine |
| X00826 | ค่าฉายรังสี Stereotactic Radiosurgery or Stereotactic Radiotherapy | Stereotactic radiosurgery/radiotherapy |
| X00827 | ค่าฉายรังสี Stereotactic Radiosurgery or Stereotactic Radiotherapy | Stereotactic radiosurgery/radiotherapy |
| X00829 | ค่าฉายรังสี Stereotactic for Brain/Spine 25 fractions | Stereotactic radiotherapy — Brain/Spine, 25 fractions |
| X00833 | ค่าฉายรังสี Stereotactic Body Radiotherapy (SBRT) with Synchrony | SBRT with Synchrony |
| X00974 | การฉายรังสี IMRT | IMRT |
| X01372 | การฉายรังสีด้วย Orthovoltage | Orthovoltage radiotherapy |
| X01374 | การฉายรังสี 2 มิติด้วยเครื่อง Linac (Electron) | 2D Linac radiotherapy (Electron) |
| X01375 | การฉายรังสี 3D-CRT (Fraction) | 3D-CRT radiotherapy |
| X01376 | การฉายรังสี IMRT (Fraction) | IMRT (per fraction) |
| X01378 | การฉายรังสี SRT (Course) | Stereotactic radiotherapy (per course) |
| X01380 | การฉายรังสี 4 มิติ (Fraction) | 4D radiotherapy |
| X01557 | การฝังเครื่องมือรังสีระยะใกล้ | Brachytherapy device implantation |
| X01558 | การใส่และการฝังเครื่องมือรังสีระยะใกล้ | Brachytherapy device insertion and implantation |
| X01561 | การให้รังสีระยะใกล้ | Brachytherapy delivery |
| X01562 | การให้รังสีระยะใกล้ แบบแผ่นที่ตา | Eye plaque brachytherapy |

> [!NOTE]
> These billing codes cover all radiotherapy delivery procedures at Ramathibodi Hospital and are not restricted by body site. Among these, X00825, X00826, X00827, and X00829 explicitly relate to brain/spine radiotherapy. Full restriction to brain radiotherapy for all modality codes requires linkage with co-occurring brain tumour or brain metastasis diagnosis codes, and is deferred to a subsequent meeting.

#### Merging into Inferred Diagnosis

Patients who pass all applicable exclusion criteria — from either or both the AChEI and Memantine groups — are labelled **Unspecified (Inferred)**. This group is subsequently merged with **Unspecified (Diagnosed)** patients (ICD-10 code F03) into a single **Unspecified** subtype at final label assignment, as described in the [Subtype Classification](#subtype-classification) section.

### Merging for Final Cohort

Following the application of exclusion criteria to the medication arm, patients are consolidated into three groups:

1. Patients with ICD-10 dementia codes only (*n* = —)
2. Patients with both ICD-10 dementia codes and qualifying anti-dementia medication prescriptions (*n* = —)
3. Patients with qualifying anti-dementia medication prescriptions only — **Unspecified (Inferred)** (*n* = —)

All three groups are included in the final dementia cohort.

### Data Format

This table serves as the primary table for cohort curation. For each patient, the following dates are recorded:

- **Diagnosis date** — the earliest date of any qualifying ICD-10 dementia code, including unspecified (F03) and subtype-specific codes
- **Subtype-specific date** — the earliest date of each subtype-specific ICD-10 code (AD, VaD, Other, Unspecified)
- **Medication date** — the earliest date of any qualifying anti-dementia medication prescription, after exclusion criteria have been applied

The **index date** is defined as the earlier of the diagnosis date and the medication date.

#### Example Data Table

| HN | Index Date | Diagnosis Date | Medication Date | AD Date | VaD Date | Other Date | Unspecified Date |
|-|-|-|-|-|-|-|-|
| 001 | 2016-08-24 | 2016-08-24 | 2016-08-24 | 2016-08-24 | — | — | — |
| 002 | 2022-10-17 | 2022-10-17 | — | — | — | 2022-10-17 | — |
| 003 | 2023-02-02 | — | 2023-02-02 | — | — | — | — |
| 004 | 2010-03-06 | 2012-09-01 | 2010-03-06 | — | 2012-09-01 | — | — |
| 005 | 2018-05-10 | 2019-03-01 | 2018-05-10 | — | — | — | 2019-03-01 |
| 006 | 2014-11-03 | 2017-06-15 | 2014-11-03 | 2017-06-15 | — | — | 2017-06-15 |
| 007 | 2012-09-12 | 2012-09-12 | — | 2012-09-12 | — | 2015-04-20 | — |

> [!NOTE]
> **Unspecified Date** refers specifically to the earliest date of an ICD-10-TM F03 diagnosis code recorded in the patient's history. It does not reflect the medication date, which is captured separately in the **Medication Date** column. Patients identified solely through medication prescription without an F03 code will have a blank Unspecified Date regardless of their subtype label.

---

## Codes Under Review

The following codes were identified during the multi-site consensus meeting as potentially relevant but requiring further review before inclusion in the dementia cohort. These codes are extracted and reported separately. The distribution of codes (*n* and %) will be presented at the next meeting to inform the decision on inclusion.

### Degenerative / Uncertain

These codes were excluded from the dementia cohort pending further review, as they may reflect neurodegenerative conditions other than dementia.

| ICD-10-TM Code | Description |
|:---|:---|
| G31\* | Other degenerative diseases of nervous system (all subcodes) |
| G312 | Progressive isolated aphasia |
| G32\* | Other degenerative disorders of nervous system in diseases classified elsewhere (all subcodes) |
| G328 | Other specified degenerative disorders of nervous system in diseases classified elsewhere |

| Code Group | Exclusion Note | *n* | % |
|:---|:---|:---|:---|
| G31\* | — | — | — |
| G31\* excluding G318 | G318 already included as Other Dementia | — | — |
| G312 | — | — | — |
| G32\* | — | — | — |
| G32\* excluding G232, G233 | G232, G233 already included as MSA | — | — |
| G328 | — | — | — |

### Mild Cognitive Impairment (MCI)

These codes cover mild cognitive impairment and related conditions. They are identified separately and are **not included** in the dementia cohort.

| ICD-10-TM Code | Description |
|:---|:---|
| F067 | Mild cognitive disorder |
| R41 | Other symptoms and signs involving cognitive functions and awareness |
| R418 | Other and unspecified symptoms and signs involving cognitive functions and awareness |

| Code Group | Exclusion Note | *n* | % |
|:---|:---|:---|:---|
| F067 | — | — | — |
| R41 | — | — | — |
| R418 | — | — | — |

### BPSD / Hallucinations

These codes may reflect behavioural and psychological symptoms of dementia (BPSD) but are not specific to dementia. Coding practice varies across institutions. They are identified separately pending review.

| ICD-10-TM Code | Description |
|:---|:---|
| R44 | Other symptoms and signs involving general sensations and perceptions |
| R440 | Auditory hallucinations |
| R441 | Visual hallucinations |
| R442 | Other hallucinations |
| R443 | Hallucinations, unspecified |
| R448 | Other and unspecified symptoms and signs involving general sensations and perceptions |
| F22 | Persistent delusional disorders |
| F220 | Delusional disorder |
| F228 | Other persistent delusional disorders |

| Code Group | Exclusion Note | *n* | % |
|:---|:---|:---|:---|
| R44 | — | — | — |
| R440 | — | — | — |
| R441 | — | — | — |
| R442 | — | — | — |
| R443 | — | — | — |
| R448 | — | — | — |
| F22 | — | — | — |
| F220 | — | — | — |
| F228 | — | — | — |

---

## Subtype Classification

Each patient is assigned two subtype labels: an **initial label** based on information available at the index date, and a **final label** based on the patient's complete longitudinal record.

### Dementia Subtypes

| Subtype | Classification Basis |
|:---|:---|
| Alzheimer's Disease (AD) | ICD-10-TM codes: F000, F001, F002, F009, G300, G301, G308, G309 |
| Vascular Dementia (VaD) | ICD-10-TM codes: F010, F011, F012, F013, F018, F019 |
| Other Dementia | ICD-10-TM codes: G318, F020, G310, F023, G232, G233, G231, F021, F022, F024, F028 |
| Unspecified Dementia | ICD-10-TM code F03, **or** prescription of anti-dementia medication without any specific subtype ICD-10 code |
| Mixed Dementia | Coexistence of two or more **specific** subtype codes (AD, VaD, or Other) recorded in the same individual |

### Initial Label

The initial label is assigned at the **index date** using only the information present at that point in time.

- **Diagnosis only** → subtype is derived directly from the ICD-10 code(s) present at index
- **Medication only** → labelled as Unspecified Dementia
- **Both diagnosis and medication** → subtype is derived from the ICD-10 code(s); medication confirms the clinical picture but does not change the subtype assignment

If multiple specific subtype ICD-10 codes (AD, VaD, or Other) from different subtypes are present at the index date, the patient is labelled **Mixed Dementia**. If a specific subtype code co-occurs with F03 or medication only, the specific subtype takes precedence and the patient is **not** labelled Mixed.

### Final Label

The final label is assigned after reviewing the patient's **complete longitudinal record**. This allows subtype refinement over time — most notably, patients initially labelled Unspecified may later accrue a specific ICD-10 diagnosis, resolving them into AD, VaD, Other, or Mixed.

The final label follows the same logic as the initial label but applied across the full observation window:

- A patient who accumulates specific subtype codes (AD, VaD, or Other) from more than one subtype at any point → **Mixed Dementia**
- A specific subtype code co-occurring with F03 or medication only → specific subtype takes precedence, **not** Mixed
- A medication-only patient who never receives a specific ICD-10 code → remains **Unspecified Dementia**
- A medication-only patient who later receives a specific ICD-10 code → reclassified to that subtype (or Mixed if multiple specific subtypes)

#### Example Data Table (Labelled)

**Referring to the [example data table](#example-data-table) above,** the initial and final labels are determined as follows:

- HN 001 had an AD diagnosis at index (2016) and was also prescribed medication on the same day → initial label is AD, final label remains AD.
- HN 002 had an Other subtype diagnosis at index (2022); no other diagnosis came later → initial label is Other, final label remains Other.
- HN 003 remained medication-only throughout → Unspecified at both time points.
- HN 004 was identified first by medication (2010); a VaD diagnosis came later (2012) → initial label is Unspecified, final label resolves to VaD.
- HN 005 was identified first by medication (2018); an F03 (Unspecified) diagnosis came later (2019) → initial label is Unspecified, final label remains Unspecified.
- HN 006 was identified first by medication (2014); an AD diagnosis and F03 code arrived together (2017) → final label is AD, not Mixed, as the specific subtype takes precedence over Unspecified.
- HN 007 had an AD diagnosis at index (2012) and later accrued an Other subtype diagnosis (2015) → final label becomes Mixed.

| HN | Index Date | Diagnosis Date | Medication Date | AD Date | VaD Date | Other Date | Unspecified Date | Initial Label | Final Label |
|-|-|-|-|-|-|-|-|-|-|
| 001 | 2016-08-24 | 2016-08-24 | 2016-08-24 | 2016-08-24 | — | — | — | Both / AD | Both / AD |
| 002 | 2022-10-17 | 2022-10-17 | — | — | — | 2022-10-17 | — | Diagnosis / Other | Diagnosis / Other |
| 003 | 2023-02-02 | — | 2023-02-02 | — | — | — | — | Medication / Unspecified | Medication / Unspecified |
| 004 | 2010-03-06 | 2012-09-01 | 2010-03-06 | — | 2012-09-01 | — | — | Medication / Unspecified | Both / VaD |
| 005 | 2018-05-10 | 2019-03-01 | 2018-05-10 | — | — | — | 2019-03-01 | Medication / Unspecified | Both / Unspecified |
| 006 | 2014-11-03 | 2017-06-15 | 2014-11-03 | 2017-06-15 | — | — | 2017-06-15 | Medication / Unspecified | Both / AD |
| 007 | 2012-09-12 | 2012-09-12 | — | 2012-09-12 | — | 2015-04-20 | — | Diagnosis / AD | Diagnosis / Mixed |

---

## Final Cohort

All patients meeting either inclusion criterion are included in the **CEB Data Warehouse – Dementia Theme**. Only adult patients aged **18 years or older** on the index date are included. The cohort covers the period from **1 January 2010 to 31 December 2025**.

---

## Subtype Distribution

> [!NOTE]
> The following tables are based on data identified up to 31 December 2025, and may not reflect any subsequent data additions or corrections.

### Distribution

The table below shows the number of patients (*n*) and percentage (%) by subtype at index date and at final observation.

| Subtype | Index *n* (%) | Final *n* (%) |
|:---|:---|:---|
| Alzheimer's Disease | — | — |
| Vascular Dementia | — | — |
| Unspecified | — | — |
| Other Dementia | — | — |
| Mixed Dementia | — | — |
| **Total** | **—** | **—** |

### Transitions

The table below shows how initial subtype labels transition to final subtype labels. Rows are index subtypes; columns are final subtypes. Values are *n* (%).

| Index \ Final | AD | VaD | Unspecified | Mixed | Other | **Row Total** |
|-|-|-|-|-|-|-|
| AD | — | — | — | — | — | **—** |
| VaD | — | — | — | — | — | **—** |
| Unspecified | — | — | — | — | — | **—** |
| Mixed | — | — | — | — | — | **—** |
| Other | — | — | — | — | — | **—** |
| **Column Total** | **—** | **—** | **—** | **—** | **—** | **—** |
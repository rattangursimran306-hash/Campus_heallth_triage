# Campus Health-Center Triage and Appointment Allocation Assistant for Decision Support

> **Academic B.Tech Capstone Project**  
> **Domain:** Artificial Intelligence in Healthcare Operations & Administrative Decision Support  
> **Key Disciplines:** Production Rule Engines, Priority-Based Intelligent Agents, Retrieval-Augmented Generation (RAG), Operations Research (Scheduling Algorithms), Responsible AI Governance.

---

## 1. Executive Summary & Objective

The **Campus Health-Center Triage and Appointment Allocation Assistant** is a full-stack decision-support system designed to optimize outpatient intake and consultation slot scheduling in higher education health centers.

### Core Problems Addressed:
1. **Clinical Risk in Naive FCFS Scheduling:** Traditional clinics operate on a First-Come, First-Served (FCFS) basis. Under high load, patients experiencing acute warning signs (such as acute appendiceal pain, persistent high pyrexia, or limb trauma) suffer hazardous delays behind routine administrative visits.
2. **Diagnostic Creep of Black-Box AI:** General-purpose Large Language Models (LLMs) hallucinate diagnoses, lack determinism, and pose legal and clinical liabilities when allowed to triage patients autonomously.
3. **Queue Starvation:** Naive priority systems starve low-priority routine patients indefinitely when higher-priority cases arrive continually.

### Solution Overview:
This application implements a **strictly non-diagnostic administrative decision-support system** combining:
- **Deterministic Forward-Chaining Production System:** Evaluates self-reported patient facts against documented, institutional IF-THEN rules with conflict resolution and full traceability.
- **Priority Queue Agent (`heapq`):** Dispatches consultation slots dynamically, executes immediate emergency bypass for life-safety red flags, and applies starvation aging safeguards.
- **Empirical FCFS vs. Priority Benchmarking:** Demonstrates measurable urgent wait time reductions with real-time Plotly analytics.
- **Source-Grounded RAG Pipeline:** Retrieves and cites approved guidelines (WHO, campus emergency SOPs) with zero-cost local semantic search and zero hallucinations.
- **Responsible AI Safeguards:** PII masking, uncertainty quantification, mandatory clinical justifications for staff overrides, and immutable audit logging.

---

## 2. System Architecture

```mermaid
graph TD
    User([Student / Patient]) -->|Self-Reported Symptoms & Vitals| Reg[Patient Intake & Registration]
    Reg -->|Asserts Facts| WM[Working Memory]
    
    subgraph "Production Rule Engine"
        RB[Documented Rule Base] --> IE[Inference Engine]
        WM --> IE
        IE --> CR[Conflict Resolution: Specificity & Priority Rank]
        CR --> EE[Explanation Engine & Traceability]
    end

    subgraph "Intelligent Scheduling Subsystem"
        EE -->|Priority Flag| PA[Priority Scheduling Agent]
        PA -->|Life Safety Red Flag| EmBypass[Immediate ER Escalation Bay (Wait = 0m)]
        PA -->|Min-Heap with Dynamic Aging| PQ[Priority Queue: heapq]
        PA -->|Baseline Sequential Ordering| FCFS[FCFS Baseline Scheduler]
        PQ --> Alloc[Provider Consultation Slot Allocator]
    end

    subgraph "Retrieval-Augmented Generation (RAG)"
        Docs[Approved Health Protocols & SOPs] --> Chunker[Overlapping Semantic Chunker]
        Chunker --> VStore[TF-IDF Vector Space Matrix]
        EE -->|Symptom Query| Retriever[Semantic Context Retriever]
        VStore --> Retriever
        Retriever --> Citations[Verbatim Excerpts & Document Citations]
    end

    subgraph "Persistence & Responsible AI Governance"
        Reg --> DB[(SQLite Database - WAL Mode)]
        EE --> DB
        Alloc --> DB
        Admin([Triage Nurse / Chief Medical Officer]) -->|Inspect, Review & Override| UI[Interactive Streamlit Dashboard]
        UI -->|Mandatory Justification Log| Audit[(Immutable Audit Trail)]
        DB --> UI
        Citations --> UI
    end
```

---

## 3. Technology Stack

| Layer | Technology | Rationale & Academic Significance |
| :--- | :--- | :--- |
| **Frontend UI** | Streamlit + Custom CSS | Clean, modern healthcare interface, rapid reactivity, custom design system. |
| **Backend Engine** | Python 3.13 / 3.14 | Clean object-oriented modular architecture with type hints and dataclasses. |
| **Relational Database** | SQLite (WAL Mode) | 9 normalized relational tables, ACID compliant, persistent across restarts. |
| **Rule Engine** | Custom Production System | Working Memory, documented rules, forward-chaining inference, conflict resolution. |
| **Scheduling** | Python `heapq` | Logarithmic $O(\log n)$ priority queue with arrival tie-breaking and aging. |
| **RAG Pipeline** | Scikit-Learn TF-IDF + Cosine | Lightweight, 100% offline local vector search, zero external API costs or latency. |
| **Visualizations** | Plotly Express & Graph Objects | Publication-quality interactive charts, gauge meters, and box distributions. |
| **Testing** | Pytest 8.2+ | 35 automated test cases validating 100% deterministic accuracy. |

---

## 4. Relational Database Design (9 Normalized Tables)

The database schema (`database/schema.sql`) adheres to Boyce-Codd Normal Form (BCNF) principles with explicit foreign key constraints:

```
+--------------------+       +-----------------------+       +---------------------+
|      Patients      | 1   * |    Symptom_Reports    |       |  Rule_Definitions   |
+--------------------+-------+-----------------------+       +---------------------+
| id (PK)            |       | id (PK)               |       | rule_id (PK)        |
| patient_code (UQ)  |       | patient_id (FK)       |       | category            |
| full_name          |       | symptoms_json         |       | name                |
| age                |       | duration_days         |       | condition_desc      |
| gender             |       | pain_scale (0-10)     |       | action_priority     |
| contact            |       | temperature_c         |       | clinical_rationale  |
| created_at         |       | respiratory_distress  |       | source_protocol     |
+--------------------+       | severe_chest_pain     |       | is_active           |
         |                   +-----------------------+       +---------------------+
         | 1                                                            | 1
         |                                                              |
         | *                                                            | *
+--------------------+       +-----------------------+       +---------------------+
|    Appointments    |       |  Scheduling_History   |       |   Triggered_Rules   |
+--------------------+       +-----------------------+       +---------------------+
| id (PK)            |       | id (PK)               |       | id (PK)             |
| patient_id (FK)    |       | patient_id (FK)       |       | patient_id (FK)     |
| slot_start         |       | action                |       | rule_id (FK)        |
| slot_end           |       | old_slot / new_slot   |       | trigger_timestamp   |
| provider_id        |       | old_prio / new_prio   |       | explanation         |
| priority_category  |       | reason (mandatory)    |       | facts_matched_json  |
| status             |       | changed_by            |       | is_conflict_winner  |
| algorithm          |       | changed_at            |       +---------------------+
| estimated_wait_mins|       +-----------------------+
+--------------------+
         |
         | (Administrative Oversight)
+--------------------+       +-----------------------+       +---------------------+
|    Admin_Users     |       |      Audit_Logs       |       |    RAG_Documents    |
+--------------------+       +-----------------------+       +---------------------+
| id (PK)            |       | id (PK)               |       | id (PK)             |
| username (UQ)      |       | admin_user            |       | title               |
| full_name          |       | action_type           |       | source_org          |
| role               |       | patient_id (FK)       |       | filename            |
| password_hash      |       | details               |       | total_chunks        |
| created_at         |       | timestamp             |       | uploaded_at         |
+--------------------+       +-----------------------+       +---------------------+
```

---

## 5. Production Rule Engine Specification

### Clinical Review Categories & Numeric Ranks:
1. **`EMERGENCY ESCALATION` (Rank 0):** Life-safety warning sign. Immediate bypass of clinic queue to campus emergency bay / hospital transfer.
2. **`URGENT REVIEW` (Rank 1):** Target evaluation within 15 minutes (e.g. persistent pyrexia >39°C $\ge 2$ days, acute severe abdominal distress).
3. **`HIGH PRIORITY REVIEW` (Rank 2):** Target evaluation within 45 minutes (e.g. suspected limb fracture, incapacitating migraine $\ge 8/10$).
4. **`MEDIUM PRIORITY REVIEW` (Rank 3):** Target evaluation within 120 minutes (e.g. subacute cough $>3$ days, moderate ankle sprain).
5. **`ROUTINE REVIEW` (Rank 4):** Target evaluation within 240 minutes (e.g. preventive checkup, prescription refill, minor superficial scrape).
6. **`INSUFFICIENT INFORMATION` (Rank 5):** Flags contradictory, missing, or physiologically impossible inputs (e.g. body temperature $44.5^\circ\text{C}$). Overrides non-emergency categories for direct human intake.

### Documented Rules Table:
| Rule ID | Clinical Name | IF Condition | THEN Action Priority | Reference Protocol |
| :--- | :--- | :--- | :--- | :--- |
| `R-EMERG-001` | Acute Coronary / Chest Pain | Severe substernal or radiating chest pain | `EMERGENCY ESCALATION` | SOP-EMS-001 (Sec 2) |
| `R-EMERG-002` | Severe Airway / Stridor | Acute dyspnea, stridor, or choking signs | `EMERGENCY ESCALATION` | SOP-EMS-001 (Sec 2) |
| `R-EMERG-003` | Syncope / Acute Neurological | Loss of consciousness, slurred speech | `EMERGENCY ESCALATION` | SOP-EMS-001 (Sec 2) |
| `R-EMERG-004` | Uncontrolled Hemorrhage | Profuse arterial/venous bleeding | `EMERGENCY ESCALATION` | SOP-EMS-001 (Sec 2) |
| `R-EMERG-005` | Acute Psychiatric Crisis | Active suicidal thoughts / acute crisis | `EMERGENCY ESCALATION` | SOP-MENT-004 (Sec 2) |
| `R-URGENT-001` | Persistent High Pyrexia | Temp $\ge 39^\circ\text{C}$ and duration $\ge 2$ days | `URGENT REVIEW` | SOP-TRIAGE-002 (Sec 2) |
| `R-URGENT-002` | Acute Peritoneal / Abdomen | Severe acute abdominal pain (pain $\ge 7$) | `URGENT REVIEW` | SOP-TRIAGE-002 (Sec 2) |
| `R-URGENT-003` | Dehydration Warning | Severe vomiting/diarrhea $\ge 2$ days | `URGENT REVIEW` | SOP-TRIAGE-002 (Sec 2) |
| `R-HIGH-001` | Suspected Fracture / Joint | Deformity or acute inability to bear weight | `HIGH PRIORITY REVIEW` | SOP-TRIAGE-002 (Sec 3) |
| `R-HIGH-002` | Incapacitating Migraine | Acute headache severity $\ge 8/10$ | `HIGH PRIORITY REVIEW` | SOP-TRIAGE-002 (Sec 3) |
| `R-HIGH-003` | Spreading Soft-Tissue Infection | Spreading erythema or purulent cellulitis | `HIGH PRIORITY REVIEW` | SOP-TRIAGE-002 (Sec 3) |
| `R-MED-001` | Subacute Respiratory Illness | Cough $>3$ days with low fever $<38.5^\circ\text{C}$ | `MEDIUM PRIORITY REVIEW` | SOP-RESP-003 (Sec 3) |
| `R-MED-002` | Moderate Sprain Without Deformity | Mild-moderate sprain, pain $<7/10$ | `MEDIUM PRIORITY REVIEW` | SOP-TRIAGE-002 (Sec 4) |
| `R-MED-003` | Uncomplicated Gastroenteritis | Diarrhea or vomiting $<2$ days | `MEDIUM PRIORITY REVIEW` | SOP-TRIAGE-002 (Sec 4) |
| `R-ROUTINE-001`| Preventive / Routine Consult | Checkup, prescription refill, minor cut | `ROUTINE REVIEW` | SOP-TRIAGE-002 (Sec 5) |
| `R-INSUFFICIENT-001` | Incomplete / Contradictory Data | 0 symptoms, negative duration, temp $>43^\circ\text{C}$ | `INSUFFICIENT INFORMATION` | SOP-TRIAGE-002 (Sec 6) |

---

## 6. Priority-Based Scheduling Agent & Mathematical Formulations

### Min-Heap Priority Queue & Aging
Patients are queued in a min-heap structure via Python's standard `heapq`. The heap key is a 5-element tuple:
$$\text{Key} = \left( R_{\text{effective}}, T_{\text{arrival}}, \text{counter}, \text{patient\_data}, \text{aging\_intervals} \right)$$

#### Starvation Prevention (Aging Formula):
To prevent lower-priority routine patients from experiencing starvation during continuous arrivals of higher-priority patients:
$$R_{\text{effective}} = \max\left(0.5, R_{\text{base}} - \left\lfloor \frac{T_{\text{wait}}}{\theta_{\text{aging}}} \right\rfloor \times \Delta_{\text{boost}}\right)$$
*Default parameters:* $\theta_{\text{aging}} = 30\text{ minutes}$, $\Delta_{\text{boost}} = 0.5\text{ rank points}$.

### Empirical Comparative Metrics:
$$\text{Average Wait Time} = \frac{1}{N} \sum_{i=1}^N (T_{\text{slot\_start}}^{(i)} - T_{\text{arrival}}^{(i)})$$

$$\text{Urgent Wait Time Reduction (\%)} = \left(\frac{\bar{W}_{\text{FCFS}}^{\text{urgent}} - \bar{W}_{\text{Priority}}^{\text{urgent}}}{\bar{W}_{\text{FCFS}}^{\text{urgent}}}\right) \times 100$$

---

## 7. Retrieval-Augmented Generation (RAG) Knowledge Pipeline

1. **Source Documents:** Approved protocols stored under `knowledge_base/documents/`:
   - `campus_emergency_escalation_protocol.txt` (EMS transfer criteria)
   - `triage_warning_signs_guidelines.txt` (Manchester & WHO ambulatory triage criteria)
   - `respiratory_and_infectious_guidelines.txt` (Droplet isolation & flu protocol)
   - `mental_health_urgent_assessment.txt` (Psychological crisis SOP)
2. **Chunking & Indexing:** Paragraph-aware chunking with 450-character chunks and 60-character sliding overlap.
3. **Local Vector Search:** Sublinear TF-IDF vectorizer ($n$-gram range 1 to 2) with cosine similarity ranking.
4. **Attribution:** Citations identify the exact source organization, document filename, and section index.
5. **Safety Fallback:** Queries below the similarity threshold ($0.08$) trigger an explicit notice that no matching guidelines exist, preventing clinical hallucinations.

---

## 8. Responsible AI & Governance

- **Strict Non-Diagnostic Policy:** Clear disclaimers appear persistently across all views.
- **Human-in-the-Loop Override:** Staff can override any priority tier, but **must** supply a documented clinical rationale ($\ge 10$ characters).
- **Uncertainty Quantification:** Evaluates missing duration, vague text descriptions, and pain-symptom discrepancies, assigning an uncertainty score ($0.0$ to $1.0$).
- **PII Privacy Protection:** Supports role-based masking (e.g. `Aarav Mehta` $\rightarrow$ `A. M***`, `+91-9876543210` $\rightarrow$ `******3210`) for public or student demonstration modes.
- **Audit Trails:** All overrides, status transitions, and system events are immutably logged with timestamps and administrator usernames in `Audit_Logs`.

---

## 9. Verification & Automated Test Suite

A comprehensive test suite is located under `tests/`:

```bash
# Run the test suite via terminal
python -m pytest tests/ -v
```

### Test Suite Summary (35 Tests, 100% Passing):
1. `tests/test_rules.py` (12 tests): Individual rules, conflict resolution, missing data, contradictory inputs.
2. `tests/test_scheduler.py` (6 tests): FCFS arrival sequence, priority rank preservation, arrival tie-breaking, emergency bypass, starvation aging, mathematical precision.
3. `tests/test_rag.py` (6 tests): Document indexing, emergency retrieval, respiratory retrieval, irrelevant query suppression, citation formatting, safety fallback.
4. `tests/test_database.py` (4 tests): 9-table schema presence, CRUD operations, audit log recording, appointment status updates.
5. `tests/test_responsible_ai.py` (7 tests): Disclaimer integrity, emergency notice, uncertainty scoring, override validation, PII masking.

---

## 10. Installation & Execution Guide

### Prerequisites
- macOS (arm64 or x86_64) or Windows 10/11
- Python 3.10, 3.11, 3.12, or 3.13

### Step-by-Step Setup

```bash
# 1. Clone or navigate to the project directory
cd /Users/gursimranrattan/antigravity/scratch/campus_health_assistant

# 2. Create and activate a Python virtual environment
python3 -m venv .venv
source .venv/bin/activate    # On Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Initialize and seed database with 50 synthetic patients
python database/seed_data.py

# 5. Run the automated test suite
pytest tests/ -v

# 6. Launch the Streamlit application
streamlit run app.py
```

The web dashboard will open in your default browser at **`http://localhost:8501`**.

---

## 11. Assumptions & Limitations

1. **Non-Diagnostic Assumption:** The system assumes that self-reported inputs represent patient perception, not verified medical facts. Clinical review by qualified personnel remains mandatory prior to treatment.
2. **Synthetic Data for Evaluation:** Performance metrics and clinical histories use de-identified synthetic patient cohorts generated for university demonstration purposes.
3. **Queue Scope:** The scheduling model simulates day-clinic consultation slots. Emergency department resuscitations are assumed to occur in a dedicated acute care facility outside normal provider scheduling capacity.
4. **Offline RAG Architecture:** The default semantic retriever utilizes a local TF-IDF cosine vector space to guarantee zero operational costs and zero external network latency. An optional LLM API key can be configured in `Settings` for narrative generation.

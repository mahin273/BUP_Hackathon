# BUP_Hackathon — GridWise LLM

[![BUP CSE Fest 2026](https://img.shields.io/badge/BUP%20CSE%20Fest-2026%20Hackathon-blue.svg)](https://bup.edu.bd)
[![Association](https://img.shields.io/badge/In%20Association%20With-Poridhi-teal.svg)](https://poridhi.com)
[![Python Version](https://img.shields.io/badge/Python-3.11%2B-3776AB.svg?logo=python&logoColor=white)](https://www.python.org)
[![Framework](https://img.shields.io/badge/API-FastAPI-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Validation](https://img.shields.io/badge/Validation-Pydantic%20v2-E92063.svg?logo=pydantic&logoColor=white)](https://docs.pydantic.dev)
[![Solver](https://img.shields.io/badge/Optimizer-SciPy%20(HiGHS)-8CAAE6.svg?logo=scipy&logoColor=white)](https://scipy.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> **Smart Campus Energy Optimization Challenge (LLM-Assisted Operator Directive Interpretation)**  
> Developed for the **BUP CSE FEST Hackathon 2026** Preliminary Round in association with **Poridhi**.

---

## 📌 Table of Contents

- [Overview](#-overview)
- [System Architecture](#-system-architecture)
- [Key Features & Endpoints](#-key-features--endpoints)
- [Supported Directives & Operator Notes](#-supported-directives--operator-notes)
- [Mathematical Formulation & Optimization Model](#-mathematical-formulation--optimization-model)
- [Guardrails & Fail-Safe Engineering](#-guardrails--fail-safe-engineering)
- [API Contract & Schema Specification](#-api-contract--schema-specification)
  - [`GET /health`](#get-health)
  - [`POST /optimize-energy`](#post-optimize-energy)
- [Tech Stack](#-tech-stack)
- [Project Directory Structure](#-project-directory-structure)
- [Getting Started & Local Setup](#-getting-started--local-setup)
- [Quality Assurance & Replay Validator](#-quality-assurance--replay-validator)
- [Team & Module Ownership](#-team--module-ownership)

---

## 📖 Overview

At Bangladesh University of Professionals (BUP), smart campus electrical operations draw power from three primary sources:
1. **The Utility Grid** (time-of-use variable tariff in BDT/kWh)
2. **Rooftop Solar PV Generation** (intermittent green energy)
3. **Battery Energy Storage System (BESS)** (arbitrage and reserve capacity)

In dynamic campus operations, human facility operators issue natural-language operational notes (e.g., scheduled panel washings, sudden grid import caps, temporary emergency battery reserve requirements, or unrelated cafeteria announcements). 

**GridWise** is a resilient microgrid scheduling microservice powered by **Python, FastAPI, and SciPy**. It interprets unstructured operator directives via Generative AI (Google Gemini / Groq), validates them through strict deterministic guardrails, executes an exact Linear Program (LP) using SciPy's HiGHS solver to minimize total electricity expenditures, and independently replays the schedule against physical grid laws prior to transmission.

---

## 🏗 System Architecture

The core engineering principle of GridWise is: **"Human notes are never trusted directly as math."**  
Natural language is parsed into rigid structured schemas, sanitized by deterministic guardrails, optimized via Linear Programming, and verified by an internal replay engine.

```mermaid
flowchart LR
    A["POST /optimize-energy\n(24h Scenario + Notes)"] --> B["FastAPI + Pydantic\n(Request Validation & Integrity)"]
    B --> C["LLM Interpreter\n(Structured JSON Extraction)"]
    C --> D["Guardrail Validator\n(Clamp, Dedupe, Downgrade to no_op)"]
    D --> E["LP Optimizer\n(SciPy HiGHS Solver / Greedy Fallback)"]
    E --> F["Replay Validator\n(Physics Recheck & Recalculation)"]
    F --> G["JSON Response\n(HTTP 200 Plan + Interpretations)"]
```

### End-to-End Processing Stages:
1. **Request Validation (`Pydantic v2`)**: Validates input structure, ensuring exactly 24 continuous hourly entries (hours 0 through 23) and valid battery physical constants. Rejects malformed payloads with HTTP 400/422.
2. **LLM Interpreter**: Transforms 1–3 unstructured operator strings into machine-verifiable directives using forced structured schema generation with strict timeout budgets.
3. **Guardrail Sanitizer**: Validates LLM outputs against domain rules (e.g., verifying interval hours are ascending and in 0..23, solar factor between 0.0 and 1.0, non-negative grid bounds). Degrades malformed/hallucinated items to `no_op` without crashing.
4. **Linear Programming Engine (`scipy.optimize.linprog`)**: Formulates and solves the multi-variable cost optimization model over the 24-hour horizon with exact HiGHS simplex/interior-point algorithms. Features an autonomous greedy heuristic fallback for 100% service availability.
5. **Replay Engine**: Replays physical equations, re-sums grid quantities and electricity costs from rounded plan values, and guarantees battery neutrality before returning the response.

---

## ⚡ Supported Directives & Operator Notes

Each scenario includes 1 to 3 operator notes. The system classifies relevant operational changes or flags distractors as `no_op`.

| Directive Type | Purpose | Structured Adjustment Schema | Mathematical Effect on Solver |
| :--- | :--- | :--- | :--- |
| `solar_reduction` | Temporary degradation in solar yield (cleaning, shading) | `{"hours": [int...], "factor": number}` | `effective_solar[h] = original_solar[h] * factor` |
| `minimum_battery_reserve` | Emergency backup reserve floor | `{"hours": [int...], "minimum_energy_kwh": number}` | `battery_energy_after[h] >= max(base_min, directive_min)` |
| `no_charge_window` | Prohibits battery charging | `{"hours": [int...]}` | `battery_charge_kwh[h] = 0` |
| `no_discharge_window` | Prohibits battery discharging | `{"hours": [int...]}` | `battery_discharge_kwh[h] = 0` |
| `max_grid_window` | Substation peak-demand limitation | `{"hours": [int...], "max_grid_kwh": number}` | `grid_kwh[h] <= max_grid_kwh` |
| `no_op` | Irrelevant notice / distractor note | `null` | No modification to base model |

> **Semantic Rules:**
> - `applies = false` is strictly assigned **only** to `no_op` directives. All other valid directives require `applies = true`.
> - Time intervals are zero-indexed half-open ranges: "1 PM to 3 PM" corresponds to hours `[13, 14]`.
> - Hours must be returned as strictly unique, sorted ascending integers in `[0, 23]`.
> - In `solar_reduction`, `factor` represents the **usable remaining fraction** (e.g., an "80% drop" corresponds to `factor: 0.20`).

---

## 📐 Mathematical Formulation & Optimization Model

### 1. Objective Function
Minimize the total grid electricity expenditure over the 24-hour horizon:

$$\min \quad \sum_{h=0}^{23} \left( P_{\text{grid}}[h] \cdot T[h] \right)$$

*In code terms:*
$$\min \sum_{h=0}^{23} \left( \text{grid}[h] \times \text{tariff}[h] \right)$$

### 2. Hourly Energy Balance Equation
For every hour $h \in \{0, \dots, 23\}$, energy balance must hold exactly:

$$P_{\text{grid}}[h] + P_{\text{solar}}[h] + P_{\text{discharge}}[h] = P_{\text{demand}}[h] + P_{\text{charge}}[h]$$

```text
grid_kwh[h] + solar_used_kwh[h] + battery_discharge_kwh[h] = demand_kwh[h] + battery_charge_kwh[h]
```

### 3. Solar Utilization & Curtailment
Grid export is disabled. Excess solar beyond campus demand and available battery charge rate is curtailed:

$$0 \le P_{\text{solar}}[h] \le P_{\text{solar,eff}}[h]$$

```text
0 <= solar_used_kwh[h] <= effective_solar_kwh[h]
```

### 4. Battery State-of-Charge Dynamics
Let $E[h]$ denote the stored battery energy at the end of hour $h$:

$$E[h] = E[h-1] + P_{\text{charge}}[h] - P_{\text{discharge}}[h] \quad (E[-1] = E_{\text{initial}})$$

Subject to physical bounds:
- **Energy Limits:** $\max(E_{\text{min}}, E_{\text{reserve}}[h]) \le E[h] \le E_{\text{capacity}}$
- **Throughput Limits:**  
  $0 \le P_{\text{charge}}[h] \le P_{\text{charge,max}}$  
  $0 \le P_{\text{discharge}}[h] \le P_{\text{discharge,max}}$
- **Action Mutual Exclusivity:** Battery cannot charge and discharge simultaneously; action is strictly one of `charge`, `discharge`, or `idle`. If `idle`, magnitude must equal `0.0`.
- **End-of-Day Neutrality:** The battery cannot be depleted as a one-time subsidy:
  $$E[23] = E_{\text{initial}}$$

---

## 🛡 Guardrails & Fail-Safe Engineering

To withstand unannounced judge stress tests and edge cases, GridWise implements layered defensive programming:

1. **LLM Hallucination Suppression:**
   - Any unlisted directive type is caught by the guardrail validator and normalized to `no_op`.
   - Missing or duplicate `note_index` items are re-indexed and backfilled with neutral fallbacks.
   - Out-of-bounds parameters (e.g., negative reserves, factors > 1.0) are clamped or demoted to `no_op`.
2. **Execution Timeout & Fallback:**
   - LLM calls are bounded by strict HTTP client timeouts. If the AI provider is slow, exhausted, or unreachable, notes seamlessly fall back to deterministic regex / `no_op` rather than failing the request.
3. **High-Precision SciPy Solver:**
   - Leveraging `scipy.optimize.linprog(method="highs")` ensures fast, reliable LP solutions without floating-point artifacts.
   - If the linear solver ever fails or encounters an infeasible boundary, a greedy heuristic fallback (charging during lowest tariff hours, discharging during peak pricing) ensures a valid schedule is always returned.
4. **Precision Consistency:**
   - Values are rounded to 2 decimal places (0.01 kWh / 0.01 BDT tolerance). Aggregate summaries (`total_cost_bdt`, `total_grid_kwh`, `peak_grid_kwh`) are re-calculated directly from the final rounded plan to eliminate floating-point discrepancy.

---

## 🔌 API Contract & Schema Specification

### `GET /health`
Validates service liveness.

**Response (`200 OK`):**
```json
{
  "status": "ok"
}
```

---

### `POST /optimize-energy`
Primary scheduling endpoint.

#### Request Schema (Excerpt)
```json
{
  "scenario_id": "GRID-BUP-01",
  "operator_notes": [
    "Solar output will drop to about 20% from 1 PM to 3 PM.",
    "Do not charge the battery between 2 PM and 4 PM.",
    "The cafeteria menu changes tomorrow."
  ],
  "hours": [
    { "hour": 0, "demand_kwh": 180, "solar_kwh": 0, "tariff_bdt_per_kwh": 7.0 },
    "... 22 more hours ...",
    { "hour": 23, "demand_kwh": 200, "solar_kwh": 0, "tariff_bdt_per_kwh": 9.0 }
  ],
  "battery": {
    "capacity_kwh": 500,
    "initial_energy_kwh": 200,
    "minimum_energy_kwh": 50,
    "max_charge_kwh_per_hour": 100,
    "max_discharge_kwh_per_hour": 100
  }
}
```

#### Response Schema (Excerpt)
```json
{
  "scenario_id": "GRID-BUP-01",
  "directive_interpretation": [
    {
      "note_index": 0,
      "applies": true,
      "directive_type": "solar_reduction",
      "structured_adjustment": {
        "hours": [13, 14],
        "factor": 0.2
      },
      "explanation": "Solar output curtailed to 20% during hours 13 and 14."
    },
    {
      "note_index": 1,
      "applies": true,
      "directive_type": "no_charge_window",
      "structured_adjustment": {
        "hours": [14, 15]
      },
      "explanation": "Battery charging prohibited during hours 14 and 15."
    },
    {
      "note_index": 2,
      "applies": false,
      "directive_type": "no_op",
      "structured_adjustment": null,
      "explanation": "Cafeteria update has no bearing on campus electrical operations."
    }
  ],
  "hourly_plan": [
    {
      "hour": 0,
      "grid_kwh": 180.0,
      "solar_used_kwh": 0.0,
      "battery_action": "idle",
      "battery_kwh": 0.0,
      "battery_energy_after_kwh": 200.0
    }
  ],
  "total_grid_kwh": 3420.50,
  "total_cost_bdt": 28450.00,
  "peak_grid_kwh": 250.00,
  "plan_summary": "Applied solar curtailment and charging constraints; shifted battery discharge to peak evening tariff hours while guaranteeing end-of-day neutrality."
}
```

---

## 💻 Tech Stack

- **Runtime Environment:** Python 3.11+
- **API Framework:** FastAPI
- **Data Validation:** Pydantic v2
- **Linear Programming Solver:** SciPy (`scipy.optimize.linprog`, HiGHS solver) / PuLP
- **LLM Integration:** Google GenAI SDK (`google-genai` / `google-generativeai`) & Groq API with Pydantic structured output
- **ASGI Server:** Uvicorn
- **Testing & QA:** Pytest + Requests / HTTPX
- **Deployment Platform:** Railway / Render / Fly.io

---

## 📂 Project Directory Structure

```text
├── app/
│   ├── __init__.py
│   ├── config.py           # Environment variables and service configuration
│   ├── main.py             # FastAPI entrypoint (/health, /optimize-energy)
│   ├── schemas.py          # Pydantic request/response models
│   ├── interpreter.py      # LLM note interpretation (Gemini / Groq / Fallback)
│   ├── guardrails.py       # Deterministic LLM output sanitization
│   ├── optimizer.py        # SciPy HiGHS LP formulation & greedy fallback
│   └── validator.py        # Final replay engine & numerical consistency check
├── tests/
│   ├── test_api.py         # End-to-end API testing
│   ├── test_optimizer.py   # Solver constraint validation
│   └── test_interpreter.py # LLM and regex parsing tests
├── requirements.txt
├── Procfile
├── .gitignore
└── README.md
```

---

## 🚀 Getting Started & Local Setup

### 1. Prerequisites
- Python >= 3.11
- pip

### 2. Installation
```bash
# Clone the repository
git clone git@github.com:mahin273/BUP_Hackathon.git
cd BUP_Hackathon

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration
Create a `.env` file in the project root:
```env
PORT=8000
GEMINI_API_KEY=your_free_google_ai_studio_key_here
# Optional Groq fallback
GROQ_API_KEY=your_groq_key_here
```

### 4. Run Development Server
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Interactive OpenAPI docs will be available at: `http://localhost:8000/docs`

---

## 🧪 Quality Assurance & Replay Validator

The test suite validates both language interpretation accuracy and physical power dispatch consistency across standard and adversarial test cases:

```bash
# Run test suite
pytest -v
```

**Automated Replay Checks:**
- [x] Full energy balance satisfaction across all 24 hours (±0.01 kWh)
- [x] Exact battery end-of-day neutrality (`E[23] == initial_energy_kwh`)
- [x] Strict adherence to battery rate limits and minimum state-of-charge bounds
- [x] Solar utilization never exceeding effective adjusted solar capacity
- [x] Verified zero battery throughput during `idle` status
- [x] Independent recalculation of `total_cost_bdt`, `total_grid_kwh`, and `peak_grid_kwh`

---

## 👥 Team & Module Ownership

| Member | Focus Area | Core Responsibilities |
| :--- | :--- | :--- |
| **Mahin** (Lead) | **Optimization & Core Engine** | SciPy LP formulation (HiGHS), guardrail sanitization, replay validation, and pipeline integration |
| **Asif** | **LLM Interpretation** | Prompt engineering, structured schema enforcement, edge-case phrasing handling, safe fallbacks |
| **Tarek** | **API & Cloud Deployment** | FastAPI route scaffolding, Pydantic validation, global error handling, cloud hosting |
| **Ramim** | **Test Harness & QA** | Pytest evaluation scripts, stress-testing against hidden permutations, regression testing |

---

## 📜 Acknowledgments

Developed for the **BUP CSE FEST HACKATHON 2026**, organized by the Department of Computer Science and Engineering, **Bangladesh University of Professionals (BUP)**, in association with **Poridhi**.

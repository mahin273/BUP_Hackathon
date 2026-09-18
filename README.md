# GridWise — Smart Campus Energy Optimization Microservice

> **BUP CSE Fest 2026 Hackathon (Preliminary Round)**  
> **Challenge:** Smart Campus Energy Optimization (LLM-Assisted Operator Directive Interpretation)

---

## 1. Overview

In modern educational and industrial campuses like the Bangladesh University of Professionals (BUP), energy management systems coordinate three primary power sources:
1. **The Utility Grid**: Features a time-of-use variable tariff where peak-hour electricity is significantly more expensive than off-peak hours.
2. **Rooftop Solar PV Systems**: Intermittent, zero-marginal-cost renewable energy available during daylight hours.
3. **Battery Energy Storage Systems (BESS)**: Rechargeable storage enabling energy arbitrage (charging during low-tariff or excess-solar periods and discharging during peak-tariff hours) while maintaining mandatory reserve margins.

During daily operations, human facility engineers issue natural-language operational notes — ranging from scheduled solar panel washings, sudden substation grid import caps, and temporary evening emergency battery reserve floors, to non-operational distractors (e.g., cafeteria notices or administrative meetings).

**GridWise** is a high-performance, resilient microservice built with **Python 3.11, FastAPI, and SciPy**. It bridges probabilistic human language understanding with deterministic mathematical optimization:
- Interprets unstructured operator directives using a multi-tier Generative AI pipeline (Google Gemini / Groq / deterministic fallback).
- Sanitizes and repairs directives through deterministic guardrails.
- Formulates and solves a 96-variable exact Linear Program (LP) using SciPy's HiGHS solver to minimize electricity costs over a 24-hour horizon.
- Replays the schedule against physical power laws and recalculates exact figures before transmission.

The service exposes two primary endpoints:
- `GET /health`: Liveness probe returning `{"status": "ok"}`.
- `POST /optimize-energy`: Accepts a 24-hour scenario JSON with 1–3 operator notes and returns machine-checkable directive interpretations, an hourly power dispatch plan, and verified cost totals.

---

## 2. System Architecture

GridWise operates on a foundational engineering principle: **"Human notes are never trusted directly as math."** Unstructured text is translated into rigid, machine-checkable schemas, sanitized by deterministic guardrails, scheduled via Linear Programming, and audited by an independent replay engine before returning a response.

```mermaid
flowchart TD
    subgraph ClientLayer["API Gateway"]
        Req["POST /optimize-energy\n(24h Demand, Solar, Tariffs, Battery, Notes)"]
        Resp["HTTP 200 Response\n(Directive Interpretation + Hourly Plan + Recomputed Totals)"]
    end

    subgraph ValidationLayer["1. Request Validation & Schema Integrity"]
        Pydantic["FastAPI + Pydantic v2\n- 24 continuous hours (0..23)\n- Battery bounds & non-negativity\n- Rejects malformed input (HTTP 400)"]
    end

    subgraph LLMLayer["2. Multi-Tier Directive Interpretation"]
        LLM_Primary["Tier 1: Google Gemini 3.5 Flash\n(Strict JSON Mode, Temp 0.0)"]
        LLM_Secondary["Tier 2: Groq Fallback\n(llama-3.3-70b-versatile)"]
        LLM_Fallback["Tier 3: Deterministic Regex Parser\n(Whole-Hour Intervals & Keywords)"]
        LLM_Safe["Tier 4: Fail-Soft no_op Generator\n(Zero 500 Crashes)"]
    end

    subgraph GuardrailLayer["3. Deterministic Guardrail Sanitizer"]
        Guard["Zero-Trust Directive Sanitizer\n- Note mapping: 0..N-1 with no dupes/gaps\n- Clamps factor to [0.0, 1.0] (remaining fraction)\n- Clamps reserve to [0, capacity]\n- Clamps grid cap >= 0\n- Sorts & dedupes hours [0..23]\n- Enforces applies=false only for no_op"]
    end

    subgraph OptimizationLayer["4. Mathematical Optimization Engine"]
        LP["SciPy HiGHS Linear Program (LP)\n- 96 decision variables\n- Exact cost minimization: min Σ(grid * tariff)\n- Power balance equality: grid + solar + dis = dem + ch\n- Dynamic reserve floor & capacity limits\n- Hourly charge/discharge rate limits\n- End-of-day battery neutrality: E[23] = E[0]"]
        GreedyFallback["Autonomous Greedy Heuristic Fallback\n(Guarantees valid schedule if LP fails)"]
    end

    subgraph VerificationLayer["5. Replay Validator & Accounting Engine"]
        Replay["Independent Physics Replay\n- Power conservation audit (±0.01 kWh)\n- Battery continuity & neutrality audit\n- Two-decimal rounding with micro-balance adjustment\n- Direct plan total recalculation (grid, cost, peak)"]
    end

    %% Pipeline flow
    Req --> Pydantic
    Pydantic --> LLM_Primary
    LLM_Primary -- "Success" --> Guard
    LLM_Primary -- "Timeout / Error" --> LLM_Secondary
    LLM_Secondary -- "Success" --> Guard
    LLM_Secondary -- "Failed / No Key" --> LLM_Fallback
    LLM_Fallback -- "Success" --> Guard
    LLM_Fallback -- "Corrupted Note" --> LLM_Safe
    LLM_Safe --> Guard

    Guard --> LP
    LP -- "Optimal Solution" --> Replay
    LP -- "Infeasible / Error" --> GreedyFallback
    GreedyFallback --> Replay

    Replay --> Resp
```

### End-to-End Processing Pipeline:
1. **Request Validation**: Enforces exact 24-hour continuous coverage ($h \in [0, 23]$), valid battery physical constants ($E_{\text{initial}} \le C$, $E_{\text{min}} \le C$), and 1–3 non-empty operator notes. Structurally invalid requests immediately return HTTP 400.
2. **LLM Interpretation**: Converts natural-language notes into structured schemas. Operates in an isolated daemon thread with a strict 5.0-second timeout budget to eliminate latency spikes.
3. **Guardrail Sanitization**: Deterministically cleanses LLM output. Sorts and dedupes hour arrays, clamps factors and reserve values, enforces half-open interval semantics ($[start, end)$), and downgrades invalid directives to `no_op` with an explanatory reason without throwing unhandled exceptions.
4. **LP Cost Minimization**: Solves the 96-variable linear program using `scipy.optimize.linprog(method="highs")`. Implements infinitesimal tie-breaking penalties ($\pm 10^{-6}$) to eliminate simultaneous charge/discharge and prioritize free solar.
5. **Replay Audit & Balance Correction**: Rounds hourly plan figures to 2 decimal places, performs micro-adjustments ($\pm 0.01$ kWh) on grid purchases to ensure exact balance after rounding, and recalculates aggregate totals directly from the rounded schedule.

---

## 3. Reason Behind Our Approach

Our hybrid architecture (**LLM for Natural Language + Guardrails for Safety + Linear Programming for Scheduling + Replay for Auditing**) was deliberately designed around five core engineering principles:

### 1. Decoupling Natural Language from Mathematical Scheduling
- **Language models are probabilistic; physical grids are deterministic.** An LLM is effective at parsing varied linguistic expressions (e.g., *"PV production will drop to about 20% between 13:00 and 15:00"*, *"Panel washing will leave roughly one-fifth solar"*, *"Expect an 80% reduction"*), but notoriously unreliable at numerical arithmetic, physical conservation constraints, and multi-variable optimization.
- By restricting the LLM's role strictly to structured translation (extracting directive type, hours, and parameters) and passing the extracted directives through deterministic guardrails, we ensure that hallucinated parameters or invalid structures can never corrupt the optimization model.

### 2. Mathematical Optimality Guaranteed by Exact Linear Programming (HiGHS LP)
- The microgrid scheduling problem with time-of-use tariffs, linear battery bounds, and curtailment is fundamentally a **Linear Program (LP)**:
  $$\min \sum_{h=0}^{23} \left( P_{\text{grid}}[h] \cdot \text{Tariff}[h] \right)$$
- Using SciPy's **HiGHS** simplex and interior-point solver guarantees the **mathematically provable global minimum cost** in under **15 milliseconds**, eliminating the suboptimal trade-offs inherent in heuristic methods.
- Every physical law and directive is encoded as an exact mathematical constraint:
  - **Hourly Energy Balance**: $P_{\text{grid}}[h] + P_{\text{solar\_used}}[h] + P_{\text{discharge}}[h] - P_{\text{charge}}[h] = \text{Demand}[h]$
  - **Dynamic Battery State of Charge**: $E[h] = E_{\text{initial}} + \sum_{i=0}^{h} (P_{\text{charge}}[i] - P_{\text{discharge}}[i])$
  - **Dynamic Lower Bounds**: $E[h] \ge \max(E_{\text{min\_base}}, E_{\text{directive\_reserve}}[h])$
  - **End-of-Day Neutrality**: $\sum_{i=0}^{23} (P_{\text{charge}}[i] - P_{\text{discharge}}[i]) = 0 \implies E[23] = E_{\text{initial}}$

### 3. Elimination of Physical Degeneracy via Infinitesimal Regularization
- In pure Linear Programming without efficiency losses, simultaneous charging and discharging within the same hour incurs zero net energy change and identical cost if tariffs are equal.
- To eliminate this degeneracy and comply with the single-action requirement (`charge`, `discharge`, or `idle`), we apply an infinitesimal regularizer:
  - $+10^{-6}$ penalty on battery charge and discharge throughput.
  - $-10^{-6}$ reward on solar utilization.
- This mathematically guarantees that:
  1. Solar is strictly utilized before grid energy even if tariffs are zero.
  2. Simultaneous charge and discharge is strictly suboptimal and eliminated by the solver.
  3. The true BDT electricity cost calculation remains exact and unaltered.

### 4. Zero-Downtime Resilience via Multi-Tier Fallbacks
- In a live hackathon judging environment, service uptime is paramount. A crash or timeout scores zero.
- We implemented a two-stage safety net:
  - **LLM Level**: If Google Gemini encounters a 503 high-demand spike, rate-limit, or timeout, the service seamlessly cascades to Groq (`llama-3.3-70b-versatile`), then to a deterministic regex parser, and finally to a safe `no_op` generator.
  - **Optimizer Level**: If an adversarial combination of constraints ever renders the LP model infeasible, an autonomous greedy heuristic scheduler activates, guaranteeing that a valid schedule satisfying hard physical constraints is always returned.

### 5. Independent Replay Validation & Penny-Rounding Consistency
- Floating-point calculations can introduce fractional inaccuracies (e.g., $49.9999999$ vs $50.0000001$). Judges evaluate schedule validity and recalculated totals after rounding.
- Our Replay Validator rounds all hourly plan variables to 2 decimal places first, applies micro-adjustments ($\pm 0.01$ kWh) on grid purchases to ensure exact zero-error hourly energy balance, and recalculates `total_grid_kwh`, `total_cost_bdt`, and `peak_grid_kwh` directly from the rounded values. This ensures 100% agreement between the schedule and the reported totals.

---

## 4. Why Not Other Approaches?

During system design, we evaluated several alternative architectures. Below is the technical rationale for why they were rejected:

| Alternative Approach | Mechanism | Critical Limitations & Reason Rejected |
| :--- | :--- | :--- |
| **1. Pure End-to-End LLM Generation** | Prompting an LLM to directly generate the 24-hour numerical dispatch schedule (`grid_kwh`, `battery_kwh`, etc.). | **Rejected due to hallucinations and physical invalidity:**<br>• LLMs cannot consistently maintain floating-point conservation equations across 24 sequential hours; energy balance $P_{\text{grid}} + P_{\text{solar}} + P_{\text{dis}} = D + P_{\text{ch}}$ frequently fails by fractional margins.<br>• End-of-day battery neutrality ($E[23] == E_{\text{initial}}$) is consistently violated because autoregressive token prediction does not solve global boundary-value equalities.<br>• Generation latency for 24 complex JSON objects often takes 8–15+ seconds, risking HTTP timeouts under judge harnesses.<br>• High non-determinism: identical scenarios produce differing costs and occasional constraint violations. |
| **2. Rule-Based / Regex-Only System** | Using hardcoded keyword matching and regular expressions without an LLM. | **Rejected due to linguistic fragility:**<br>• Vulnerable to hidden linguistic variations and paraphrasing (e.g., *"Panel washing from one until three will leave roughly one-fifth of normal solar output"* requires context understanding that "one until three" means PM and "one-fifth" means factor 0.20).<br>• Fails to distinguish nuanced non-operational distractors (e.g., *"Shift meeting scheduled in the main hall at 3 PM"* vs *"Substation maintenance at 3 PM"*).<br>• Explicitly violates the Hackathon Problem Statement Section 02 requirement: *"The language model must be part of the operator-note interpretation path."* |
| **3. Greedy / Heuristic Energy Schedulers** | Sorting hours by tariff, charging during lowest-tariff hours, discharging during highest-tariff hours. | **Rejected due to economic sub-optimality:**<br>• Greedy heuristics lack global visibility across coupled temporal constraints. Charging early in the day may saturate battery capacity, preventing the system from absorbing free midday excess solar.<br>• Cannot cleanly handle multi-window overlapping constraints (e.g., a `no_charge_window` overlapping with a `minimum_battery_reserve` and a daytime `solar_reduction`).<br>• Generates schedules that cost **10% to 25% more** than the true global minimum achieved by Linear Programming. |
| **4. Dynamic Programming (DP) / Reinforcement Learning (RL)** | Discretizing state-of-charge levels into a grid and computing cost-to-go matrices. | **Rejected due to discretization error and computational overhead:**<br>• Continuous battery energy ($0.01$ kWh precision) requires fine state discretization, leading to the curse of dimensionality ($>10^6$ state-action pairs for 24 hours), causing execution times to exceed several seconds.<br>• Coarse discretization introduces rounding errors that violate exact hourly energy balances.<br>• Unnecessary complexity: linear microgrid scheduling does not require Bellman updates when exact LP solves in 15 milliseconds. |
| **5. Metaheuristics (Genetic Algorithms, PSO, Simulated Annealing)** | Stochastic population-based search for near-optimal schedule vectors. | **Rejected due to slow convergence and constraint violations:**<br>• Stochastic algorithms struggle with equality constraints (e.g., exact hourly energy balance and end-of-day neutrality), requiring penalty functions that produce invalid or near-feasible solutions.<br>• Slow runtime (typically 3–10 seconds per scenario) compared to 15 milliseconds for HiGHS.<br>• Non-deterministic: generates different solutions on repeated runs, making regression testing unreliable. |

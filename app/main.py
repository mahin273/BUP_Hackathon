"""FastAPI application entrypoint for GridWise energy optimization service."""

from __future__ import annotations

import logging
from typing import Any
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse

from app.guardrails import sanitize_directives
from app.interpreter import interpret_notes
from app.optimizer import solve_energy_optimization
from app.schemas import (
    HealthResponse,
    OptimizeRequest,
    OptimizeResponse,
)
from app.validator import validate_and_recompute_plan

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("gridwise")

app = FastAPI(
    title="GridWise LLM Energy Optimization",
    description="Smart campus energy scheduling with LLM operator directive interpretation.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Returns HTTP 400 for malformed or structurally invalid request payloads."""
    logger.warning("Request validation failed: %s", exc.errors())
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": "Bad Request",
            "message": "Malformed JSON or structurally invalid request.",
            "details": [
                {
                    "loc": list(err.get("loc", [])),
                    "msg": err.get("msg", "Invalid value"),
                    "type": err.get("type", "value_error"),
                }
                for err in exc.errors()
            ],
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Safe fail-soft 500 handler that never leaks stack traces or internal secrets."""
    logger.error("Unhandled server exception during request processing: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred while processing the energy schedule.",
        },
    )


@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    """Redirect root endpoint to interactive Swagger documentation."""
    return RedirectResponse(url="/docs")


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check() -> dict[str, str]:
    """Liveness probe returning HTTP 200 with status ok."""
    return {"status": "ok"}


@app.post("/optimize-energy", response_model=OptimizeResponse, tags=["Optimization"])
async def optimize_energy(request: OptimizeRequest) -> OptimizeResponse:
    """Primary energy scheduling endpoint.
    
    1. Interprets natural-language operator notes via LLM/deterministic engine.
    2. Enforces deterministic guardrails and sanitization.
    3. Solves 24-hour cost minimization via SciPy HiGHS LP with greedy fallback.
    4. Independently audits and recalculates final figures via Replay Validator.
    5. Returns machine-checkable interpretations and validated hourly schedule.
    """
    logger.info("Processing scenario_id=%s with %d notes", request.scenario_id, len(request.operator_notes))

    # 1. Interpret operator notes
    raw_directives = interpret_notes(request.operator_notes)

    # 2. Guardrails sanitization
    sanitized_directives = sanitize_directives(
        raw_directives=raw_directives,
        num_notes=len(request.operator_notes),
        battery_capacity=request.battery.capacity_kwh,
        initial_battery_energy=request.battery.initial_energy_kwh,
    )

    # 3. Mathematical optimization
    raw_plan = solve_energy_optimization(
        hours=request.hours,
        battery=request.battery,
        directives=sanitized_directives,
    )

    # 4. Independent replay validation & recalculation
    validated_plan, total_grid, total_cost, peak_grid = validate_and_recompute_plan(
        plan=raw_plan,
        hours=request.hours,
        battery=request.battery,
        directives=sanitized_directives,
    )

    # 5. Formulate plan summary
    applied_types = [d.directive_type for d in sanitized_directives if d.applies]
    if applied_types:
        directive_summary = f"applied directives: {', '.join(applied_types)}"
    else:
        directive_summary = "no operational directives active"

    summary = (
        f"Scenario {request.scenario_id} optimized successfully ({directive_summary}). "
        f"Total grid import: {total_grid:.2f} kWh, Total cost: {total_cost:.2f} BDT, Peak demand: {peak_grid:.2f} kWh. "
        "Strict energy balance and end-of-day battery neutrality guaranteed."
    )

    return OptimizeResponse(
        scenario_id=request.scenario_id,
        directive_interpretation=sanitized_directives,
        hourly_plan=validated_plan,
        total_grid_kwh=total_grid,
        total_cost_bdt=total_cost,
        peak_grid_kwh=peak_grid,
        plan_summary=summary,
    )

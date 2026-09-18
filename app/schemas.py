"""Pydantic schemas and shared data contracts for GridWise."""

from typing import Any, Literal, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


# ==========================================
# Directive Schemas
# ==========================================

DirectiveType = Literal[
    "solar_reduction",
    "minimum_battery_reserve",
    "no_charge_window",
    "no_discharge_window",
    "max_grid_window",
    "no_op",
]

ALLOWED_DIRECTIVES: set[str] = {
    "solar_reduction",
    "minimum_battery_reserve",
    "no_charge_window",
    "no_discharge_window",
    "max_grid_window",
    "no_op",
}


class SolarReductionAdjustment(BaseModel):
    hours: list[int]
    factor: float = Field(ge=0.0, le=1.0)


class MinimumBatteryReserveAdjustment(BaseModel):
    hours: list[int]
    minimum_energy_kwh: float = Field(ge=0.0)


class WindowOnlyAdjustment(BaseModel):
    hours: list[int]


class MaxGridWindowAdjustment(BaseModel):
    hours: list[int]
    max_grid_kwh: float = Field(ge=0.0)


class DirectiveInterpretation(BaseModel):
    note_index: int = Field(ge=0, description="0-based index matching operator_notes")
    applies: bool = Field(description="True for operational directives, False only for no_op")
    directive_type: DirectiveType
    structured_adjustment: Optional[dict[str, Any]] = None
    explanation: str = Field(default="", description="Concise rationale for the interpretation")

    @model_validator(mode="after")
    def validate_applies_and_adjustment(self) -> "DirectiveInterpretation":
        if self.directive_type == "no_op":
            self.applies = False
            self.structured_adjustment = None
        else:
            self.applies = True
        return self


# ==========================================
# Input Scenario Schemas
# ==========================================

class HourInput(BaseModel):
    hour: int = Field(ge=0, le=23, description="Hour of the day 0 to 23")
    demand_kwh: float = Field(ge=0.0, description="Campus electrical demand")
    solar_kwh: float = Field(ge=0.0, description="Available rooftop solar energy")
    tariff_bdt_per_kwh: float = Field(ge=0.0, description="Electricity price from grid")


class BatteryInput(BaseModel):
    capacity_kwh: float = Field(gt=0.0, description="Maximum battery capacity in kWh")
    initial_energy_kwh: float = Field(ge=0.0, description="Starting energy level at hour 0")
    minimum_energy_kwh: float = Field(ge=0.0, description="Base reserve level never breached")
    max_charge_kwh_per_hour: float = Field(ge=0.0, description="Maximum charge rate in 1 hour")
    max_discharge_kwh_per_hour: float = Field(ge=0.0, description="Maximum discharge rate in 1 hour")

    @model_validator(mode="after")
    def validate_battery_limits(self) -> "BatteryInput":
        if self.initial_energy_kwh > self.capacity_kwh:
            raise ValueError("initial_energy_kwh cannot exceed capacity_kwh")
        if self.minimum_energy_kwh > self.capacity_kwh:
            raise ValueError("minimum_energy_kwh cannot exceed capacity_kwh")
        return self


class OptimizeRequest(BaseModel):
    scenario_id: str = Field(min_length=1, description="Unique scenario identifier")
    operator_notes: list[str] = Field(min_length=1, max_length=3, description="1 to 3 operator notes")
    hours: list[HourInput] = Field(min_length=24, max_length=24, description="Hourly entries 0 to 23")
    battery: BatteryInput

    @field_validator("operator_notes")
    @classmethod
    def validate_notes(cls, notes: list[str]) -> list[str]:
        cleaned = [n.strip() for n in notes]
        if any(len(n) == 0 for n in cleaned):
            raise ValueError("Operator notes must not be empty or whitespace only")
        return cleaned

    @field_validator("hours")
    @classmethod
    def validate_hours_sequence(cls, hours: list[HourInput]) -> list[HourInput]:
        if len(hours) != 24:
            raise ValueError("Exactly 24 hourly entries required")
        hour_set = {h.hour for h in hours}
        if hour_set != set(range(24)):
            raise ValueError("Hourly entries must cover hours 0 through 23 without gaps or duplicates")
        return sorted(hours, key=lambda h: h.hour)


# ==========================================
# Output Plan Schemas
# ==========================================

BatteryAction = Literal["charge", "discharge", "idle"]


class HourPlan(BaseModel):
    hour: int = Field(ge=0, le=23)
    grid_kwh: float = Field(ge=0.0)
    solar_used_kwh: float = Field(ge=0.0)
    battery_action: BatteryAction
    battery_kwh: float = Field(ge=0.0)
    battery_energy_after_kwh: float = Field(ge=0.0)

    @model_validator(mode="after")
    def validate_idle_action(self) -> "HourPlan":
        if self.battery_action == "idle" and abs(self.battery_kwh) > 1e-4:
            self.battery_kwh = 0.0
        return self


class OptimizeResponse(BaseModel):
    scenario_id: str
    directive_interpretation: list[DirectiveInterpretation]
    hourly_plan: list[HourPlan] = Field(min_length=24, max_length=24)
    total_grid_kwh: float = Field(ge=0.0)
    total_cost_bdt: float = Field(ge=0.0)
    peak_grid_kwh: float = Field(ge=0.0)
    plan_summary: str


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"

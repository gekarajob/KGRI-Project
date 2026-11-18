from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import AfterValidator, AwareDatetime, Field, model_validator

from apps.participants.schemas import InputModel


def normalize_capture_time(value: datetime) -> datetime:
    return value.astimezone(UTC)


CaptureTime = Annotated[AwareDatetime, AfterValidator(normalize_capture_time)]


class PhenotypeCreate(InputModel):
    participant_id: int = Field(gt=0)
    study_id: int = Field(gt=0)
    captured_at: CaptureTime = Field(default_factory=lambda: datetime.now(UTC))
    height_cm: Decimal = Field(ge=50, le=250, max_digits=6, decimal_places=2)
    weight_kg: Decimal = Field(ge=10, le=300, max_digits=6, decimal_places=2)
    systolic_bp: Decimal = Field(ge=60, le=250, max_digits=6, decimal_places=2)
    diastolic_bp: Decimal = Field(ge=30, le=150, max_digits=6, decimal_places=2)
    malaria_history: bool
    livestock_contact: bool
    notes: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_blood_pressure(self) -> "PhenotypeCreate":
        if self.systolic_bp <= self.diastolic_bp:
            raise ValueError("systolic_bp must be greater than diastolic_bp")
        return self


class PhenotypePatch(InputModel):
    participant_id: int | None = Field(default=None, gt=0)
    study_id: int | None = Field(default=None, gt=0)
    captured_at: CaptureTime | None = None
    height_cm: Decimal | None = Field(default=None, ge=50, le=250, max_digits=6, decimal_places=2)
    weight_kg: Decimal | None = Field(default=None, ge=10, le=300, max_digits=6, decimal_places=2)
    systolic_bp: Decimal | None = Field(default=None, ge=60, le=250, max_digits=6, decimal_places=2)
    diastolic_bp: Decimal | None = Field(
        default=None, ge=30, le=150, max_digits=6, decimal_places=2
    )
    malaria_history: bool | None = None
    livestock_contact: bool | None = None
    notes: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def reject_null_fields(self) -> "PhenotypePatch":
        for field in self.model_fields_set - {"notes"}:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self

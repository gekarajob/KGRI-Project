from decimal import Decimal
from typing import Literal

from pydantic import Field, model_validator

from apps.participants.schemas import InputModel

SampleType = Literal["dna", "blood", "saliva"]
Platform = Literal["ultima_ug100", "ont_promethion", "pacbio", "olink"]
SampleStatus = Literal[
    "collected",
    "shipped",
    "received_at_lab",
    "dna_extracted",
    "library_prepped",
    "sequenced",
    "qc_passed",
]


class SampleCreate(InputModel):
    participant_id: int = Field(gt=0)
    sample_type: SampleType
    platform: Platform | None = None
    batch_id: str | None = Field(default=None, min_length=1, max_length=100)
    sequencing_file_path: str | None = Field(default=None, min_length=1, max_length=500)
    mean_coverage: Decimal | None = Field(
        default=None, ge=0, le=Decimal("99999999.99"), max_digits=10, decimal_places=2
    )


class SamplePatch(InputModel):
    sample_type: SampleType | None = None
    platform: Platform | None = None
    batch_id: str | None = Field(default=None, min_length=1, max_length=100)
    sequencing_file_path: str | None = Field(default=None, min_length=1, max_length=500)
    mean_coverage: Decimal | None = Field(
        default=None, ge=0, le=Decimal("99999999.99"), max_digits=10, decimal_places=2
    )

    @model_validator(mode="after")
    def reject_null_type(self) -> "SamplePatch":
        if "sample_type" in self.model_fields_set and self.sample_type is None:
            raise ValueError("sample_type cannot be null")
        return self


class StatusChange(InputModel):
    status: SampleStatus

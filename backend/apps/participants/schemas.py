from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

Text = Annotated[str, Field(min_length=1)]


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)


class ConsentValues(InputModel):
    broad_consent: bool = False
    recontact_consent: bool = False
    data_sharing_consent: bool = False


class ConsentPatch(InputModel):
    broad_consent: bool | None = None
    recontact_consent: bool | None = None
    data_sharing_consent: bool | None = None

    @model_validator(mode="after")
    def reject_null_choices(self) -> "ConsentPatch":
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"{field} must be true or false")
        return self


class ParticipantCreate(InputModel):
    full_name: Text = Field(max_length=200)
    age: int = Field(ge=0, le=120)
    sex: str = Field(min_length=1, max_length=30)
    community: Text = Field(max_length=120)
    county: Text = Field(max_length=100)
    recruitment_site: Text = Field(max_length=120)
    consent: ConsentValues | None = None


class ParticipantPatch(InputModel):
    full_name: Text | None = Field(default=None, max_length=200)
    age: int | None = Field(default=None, ge=0, le=120)
    sex: str | None = Field(default=None, min_length=1, max_length=30)
    community: Text | None = Field(default=None, max_length=120)
    county: Text | None = Field(default=None, max_length=100)
    recruitment_site: Text | None = Field(default=None, max_length=120)
    consent: ConsentPatch | None = None

    @model_validator(mode="after")
    def reject_null_fields(self) -> "ParticipantPatch":
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self

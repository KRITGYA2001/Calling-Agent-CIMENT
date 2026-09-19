from enum import Enum

from pydantic import BaseModel


class FieldType(str, Enum):
    text = "text"
    boolean = "boolean"
    enum = "enum"
    date = "date"
    number = "number"


class JourneyField(BaseModel):
    id: str
    label: str
    ask_hint: str
    type: FieldType
    required: bool = True
    options: list[str] | None = None
    locked: bool = False  # confirm-only: voice can verify the value on file but never change it (e.g. the number we call)
    sensitive: bool = False  # never spoken back in full, never captured raw (payment details)
    # Scripts are the source of truth for what Ava asks and how she recovers.
    script: str = ""  # the question, as spoken
    reprompt: str = ""  # used when the answer was not captured / failed validation
    validation: str | None = None  # named validator: email | phone | nmi | dob | positive_number


class JourneySection(BaseModel):
    id: str
    title: str
    script: str = ""  # spoken transition into this section
    fields: list[JourneyField]


class JourneyDefinition(BaseModel):
    vertical: str
    name: str
    intro_disclosure: str
    opener_template: str  # personalised first line; {first_name} and {dropout_when} are filled per lead
    guardrails: list[str]
    escalation_scripts: dict[str, str]  # category -> what Ava says before handing off
    handoff_script: str  # what the human says when picking up
    decline_script: str
    busy_script: str
    payment_boundary_script: str
    close_script: str
    sections: list[JourneySection]

    def all_fields(self) -> list[JourneyField]:
        return [f for s in self.sections for f in s.fields]

    def field(self, field_id: str) -> JourneyField | None:
        return next((f for f in self.all_fields() if f.id == field_id), None)

    def section_of(self, field_id: str) -> JourneySection | None:
        return next((s for s in self.sections if any(f.id == field_id for f in s.fields)), None)

    def required_field_ids(self) -> set[str]:
        return {f.id for f in self.all_fields() if f.required}


class EscalationCategory(str, Enum):
    anger = "anger"
    confusion = "confusion"
    off_script = "off_script"
    sensitive_topic = "sensitive_topic"
    explicit_human_request = "explicit_human_request"
    low_confidence = "low_confidence"

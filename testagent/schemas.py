from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProjectCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    base_url: str = ""
    environment: Literal["local", "development", "staging", "production"] = "staging"


class ProjectUpdate(BaseModel):
    base_url: str
    environment: Literal["local", "development", "staging", "production"]


class RepositoryImport(BaseModel):
    location: str = Field(min_length=1)


class UiInspectRequest(BaseModel):
    path: str = "/"


class TaskCreate(BaseModel):
    project_id: str
    prompt: str = Field(min_length=5, max_length=4000)
    function: str | None = None
    run_id: str | None = None
    provider: Literal["codex", "antigravity", "claude"] | None = None
    model: str | None = Field(default=None, min_length=1, max_length=160)
    effort: str | None = Field(default=None, min_length=1, max_length=40)
    case_ids: list[str] = Field(default_factory=list, max_length=30)
    execution_mode: Literal['generate', 'run'] = 'run'
    run_mode: Literal['sequential', 'parallel'] = 'sequential'
    workers: int = Field(default=3, ge=1, le=4)
    agent_mode: Literal['auto', 'single'] = 'auto'


class AiSelection(BaseModel):
    provider: Literal["codex", "antigravity", "claude"]
    model: str = Field(min_length=1, max_length=160)
    effort: str | None = Field(default=None, min_length=1, max_length=40)


class AiLogin(BaseModel):
    device_code: bool = False


class AgentFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=3, max_length=180)
    detail: str = Field(min_length=3)
    severity: Literal["critical", "high", "medium", "low", "info"] = "info"
    evidence_ids: list[str] = Field(default_factory=list)


class AgentAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str = Field(min_length=10)
    findings: list[AgentFinding] = Field(default_factory=list, max_length=20)
    recommendations: list[str] = Field(default_factory=list, max_length=20)


class AgentSubTask(BaseModel):
    model_config = ConfigDict(extra="forbid")
    function: str = Field(min_length=1, max_length=80)
    prompt: str = Field(min_length=10, max_length=1200)


class AgentRoute(BaseModel):
    model_config = ConfigDict(extra="forbid")
    function: str = Field(min_length=1, max_length=80)
    reason: str = Field(min_length=5, max_length=1200)
    sub_tasks: list[AgentSubTask] = Field(default_factory=list, max_length=3)


class Locator(BaseModel):
    model_config = ConfigDict(extra="forbid")
    testid: str | None = None
    role: str | None = None
    name: str | None = None
    label: str | None = None
    id: str | None = None
    text: str | None = None
    css: str | None = None
    placeholder: str | None = None
    test_attribute: Literal['data-testid', 'data-test', 'data-qa'] | None = None
    exact: bool = True
    scope: Locator | None = None

    @model_validator(mode="after")
    def has_strategy(self) -> "Locator":
        if not any((self.testid, self.role, self.label, self.id, self.text, self.css, self.placeholder)):
            raise ValueError("A locator strategy is required")
        if self.scope and self.scope.scope:
            raise ValueError("Only one locator scope is supported")
        return self


class BrowserAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["navigate", "fill", "click", "check", "select", "assert_visible", "assert_text", "assert_url"]
    url: str | None = None
    target: Locator | None = None
    value: str | None = None

    @model_validator(mode="after")
    def required_fields(self) -> "BrowserAction":
        if self.action in ("navigate", "assert_url") and not self.url:
            raise ValueError(f"{self.action} requires url")
        if self.action not in ("navigate", "assert_url") and not self.target:
            raise ValueError(f"{self.action} requires target")
        if self.action in ("fill", "select", "assert_text") and self.value is None:
            raise ValueError(f"{self.action} requires value")
        return self


class Automation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actions: list[BrowserAction] = Field(min_length=1, max_length=50)


class ApiRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
    path: str
    headers: dict[str, str] = Field(default_factory=dict)
    body: dict | list | str | None = None
    expected_status: int = Field(ge=100, le=599)


class TestCaseDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    origin_case_id: str | None = None
    title: str = Field(min_length=3, max_length=180)
    level: Literal["unit", "integration", "api", "ui", "e2e"]
    type: Literal["positive", "negative", "boundary", "validation", "security", "error", "other"]
    priority: Literal["critical", "high", "medium", "low"]
    preconditions: list[str] = Field(default_factory=list)
    steps: list[str] = Field(min_length=1)
    expected: list[str] = Field(min_length=1)
    source_ids: list[str] = Field(default_factory=list)
    automation: Automation | None = None
    api_request: ApiRequest | None = None
    unit_test_code: str | None = None

    @model_validator(mode="after")
    def one_execution_engine(self) -> "TestCaseDraft":
        if sum(value is not None for value in (self.automation, self.api_request, self.unit_test_code)) > 1:
            raise ValueError("A test case must define only one execution engine")
        return self


class GeneratedPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    intent: Literal["test_generation", "api_testing", "ui_automation", "unit_testing"]
    summary: str
    risks: list[str] = Field(default_factory=list)
    cases: list[TestCaseDraft] = Field(min_length=1, max_length=20)


class RunCreate(BaseModel):
    project_id: str
    test_case_ids: list[str] = Field(min_length=1, max_length=30)
    mode: Literal['sequential', 'parallel'] = 'sequential'
    workers: int = Field(default=3, ge=1, le=4)


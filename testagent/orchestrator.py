"""LLM-only agent selection through the task's signed-in AI provider.

The model receives project context and the registered specialists, then returns
the function to call. There are no keyword rules or routing fallbacks here.
Input collection and execution validation live in separate modules.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable

from .llm import complete_json
from .routing_context import collect_routing_context
from .schemas import AgentRoute
from .skills import AgentSkill, SKILLS, compose_skill


@dataclass(frozen=True)
class RoutedSubTask:
    skill: AgentSkill
    prompt: str
    run_id: str | None
    case_ids: list[str]

    def public_dict(self) -> dict:
        return {'function': self.skill.id, 'prompt': self.prompt,
                'run_id': self.run_id, 'case_ids': self.case_ids}


@dataclass(frozen=True)
class RoutedTask:
    skill: AgentSkill
    reason: str
    run_id: str | None
    case_ids: list[str]
    sub_tasks: list[RoutedSubTask] = field(default_factory=list)

    def public_dict(self) -> dict:
        return {"requested_function": "orchestrator", "source": "ai",
                "function": self.skill.id, "reason": self.reason,
                "run_id": self.run_id, "case_ids": self.case_ids,
                "sub_tasks": [item.public_dict() for item in self.sub_tasks]}


class AgentOrchestrator:
    def __init__(self, complete: Callable[..., dict] = complete_json):
        self.complete = complete

    def route(self, project_id: str, project: dict, prompt: str, *,
              run_id: str | None = None, case_ids: list[str] | None = None,
              provider: str | None = None, model: str | None = None,
              effort: str | None = None, execution_mode: str = 'run',
              agent_mode: str = 'auto') -> RoutedTask:
        case_ids = list(dict.fromkeys(case_ids or []))
        context = collect_routing_context(project_id, run_id, case_ids)
        specialists = {skill.id: skill for skill in SKILLS if skill.mode != 'orchestration'}
        request = {
            'request': prompt, 'function': 'orchestrator', 'project': project,
            'context': context,
            'execution_mode': execution_mode,
            'agent_mode': agent_mode,
            'max_sub_tasks': 3 if agent_mode == 'auto' else 0,
            'available_functions': [skill.public_dict() for skill in specialists.values()],
            'available_sub_agents': [skill.id for skill in specialists.values() if skill.mode == 'analysis'],
        }
        instructions = ('You are the TestAgent task orchestrator. Return exactly one JSON object '
                        'with function, reason and optional sub_tasks [{function, prompt}]. '
                        'Delegate only to available_functions.\n\n') + compose_skill('orchestrator')
        decision = AgentRoute.model_validate(self.complete(
            instructions, json.dumps(request, ensure_ascii=False), provider, model, effort,
        ))
        try:
            skill = specialists[decision.function]
        except KeyError as exc:
            raise ValueError(f'AI selected an unavailable specialist: {decision.function}') from exc
        if decision.sub_tasks and (agent_mode != 'auto' or skill.mode == 'execution'):
            raise ValueError('Sub-agents are unavailable for single mode or deterministic execution')
        functions = {skill.id}
        sub_tasks = []
        for item in decision.sub_tasks:
            helper = specialists.get(item.function)
            if helper is None or helper.mode != 'analysis':
                raise ValueError(f'Sub-agent must be an available analysis specialist: {item.function}')
            if item.function in functions:
                raise ValueError('Sub-agents must have distinct roles and differ from the lead specialist')
            functions.add(item.function)
            sub_tasks.append(RoutedSubTask(
                helper, item.prompt, {'run': (context['run'] or {}).get('id')}.get(helper.requires),
                {'cases': case_ids}.get(helper.requires, []),
            ))
        return RoutedTask(skill, decision.reason,
                          {'run': (context['run'] or {}).get('id')}.get(skill.requires),
                          {'cases': case_ids}.get(skill.requires, []), sub_tasks)

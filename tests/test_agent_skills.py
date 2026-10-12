"""Check prompt contracts and runnable examples, rather than Markdown length."""
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from testagent import skills
from testagent.browser_bridge import invoke_browser
from testagent.ui_agent import validate_ui_plan


class PromptCompositionTests(unittest.TestCase):
    def test_every_instruction_file_is_used_by_a_registered_role_or_handoff(self):
        used = {'subagent-handoff.md'}
        for role in skills.SKILLS:
            used.update(skills.skill_files(role.id))
        self.assertEqual(used, {path.name for path in skills._SKILL_DIR.glob('*.md')})
        for filename in used:
            with self.subTest(instruction_file=filename):
                self.assertTrue((skills._SKILL_DIR / filename).read_text(encoding='utf-8').strip())
    def test_every_ai_role_loads_its_contract_with_the_correct_response_type(self):
        for role in skills.SKILLS:
            if role.mode == 'execution':
                continue
            with self.subTest(role=role.id):
                prompt = skills.compose_skill(role.id)
                loaded = re.findall(r'<!-- instruction file: ([^>]+) -->', prompt)
                self.assertEqual(loaded, role.public_dict()['instruction_files'])
                self.assertEqual(loaded[:2], ['automation-core.md', role.file])
                response = ('GeneratedPlan' if role.mode == 'test_cases' else
                            'AgentRoute' if role.mode == 'orchestration' else 'AgentAnalysis')
                self.assertIn(f'Active phase: final. Return {response} only.', prompt)
                if role.workflow != 'browser':
                    self.assertNotIn('automation-patterns.md', loaded)
                    self.assertNotIn('locator-mastery.md', loaded)

    def test_browser_roles_exclude_final_examples_from_live_decisions(self):
        for role in ('ui_automation', 'automation_builder', 'repair_automation'):
            with self.subTest(role=role):
                prompt = skills.compose_skill(role, phase='exploration')
                loaded = re.findall(r'<!-- instruction file: ([^>]+) -->', prompt)
                self.assertEqual(loaded, skills.skill_files(role, phase='exploration'))
                self.assertIn('locator-mastery.md', loaded)
                self.assertNotIn('automation-patterns.md', loaded)
                self.assertNotIn('example_account', prompt)
                self.assertIn('Return BrowserDecision only;', prompt)
                self.assertEqual(skills.skill_files(role), [*loaded, 'automation-patterns.md'])

    def test_missing_shared_file_stops_prompt_generation(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(skills, '_SKILL_DIR', Path(directory)):
                with self.assertRaisesRegex(RuntimeError, 'automation-core.md'):
                    skills.compose_skill('ui_automation')

    def test_empty_registered_role_stops_prompt_generation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'automation-core.md').write_text('Common rules', encoding='utf-8')
            (root / 'test-plan.md').write_text(' \n', encoding='utf-8')
            with patch.object(skills, '_SKILL_DIR', root):
                with self.assertRaisesRegex(RuntimeError, 'empty: test-plan.md'):
                    skills.compose_skill('test_plan')

    def test_unknown_function_cannot_select_an_arbitrary_file(self):
        with patch.object(Path, 'read_text') as read:
            for function in ('../config', r'..\config', 'C:/secret', 'unknown_role'):
                for loader in (skills.read_skill, skills.compose_skill, skills.skill_files):
                    with self.subTest(function=function, loader=loader.__name__):
                        with self.assertRaisesRegex(ValueError, 'Unknown agent function'):
                            loader(function)
            read.assert_not_called()

    def test_execution_cannot_be_composed_as_an_ai_prompt(self):
        self.assertEqual(skills.skill_files('run_tests'), ['suite-execution.md'])
        self.assertFalse(skills.get_skill('run_tests').public_dict()['uses_ai'])
        with self.assertRaisesRegex(ValueError, 'deterministic runner'):
            skills.compose_skill('run_tests')

    def test_empty_execution_skill_cannot_be_admitted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'suite-execution.md').write_text(' \n', encoding='utf-8')
            with patch.object(skills, '_SKILL_DIR', root):
                with self.assertRaisesRegex(RuntimeError, 'empty: suite-execution.md'):
                    skills.read_skill('run_tests')

    def test_missing_handoff_has_the_same_error_contract_as_other_skills(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(skills, '_SKILL_DIR', Path(directory)):
                with self.assertRaisesRegex(RuntimeError, 'missing: subagent-handoff.md'):
                    skills.compose_sub_agent('security')

    def test_analysis_and_unknown_phases_cannot_use_a_browser_decision_prompt(self):
        with self.assertRaisesRegex(ValueError, 'live exploration'):
            skills.compose_skill('test_plan', phase='exploration')
        with self.assertRaisesRegex(ValueError, 'Unknown skill phase'):
            skills.compose_skill('ui_automation', phase='execute_arbitrary_code')


class AutomationExampleTests(unittest.TestCase):
    def test_all_final_examples_validate_and_compile_to_playwright_typescript(self):
        path = Path(__file__).resolve().parents[1] / 'testagent/agent_skills/automation-patterns.md'
        examples = re.findall(r'```json\s*\n(.*?)\n```', path.read_text(encoding='utf-8'), re.S)
        self.assertEqual(len(examples), 2)
        for index, example in enumerate(examples):
            plan = validate_ui_plan(json.loads(example), 'http://127.0.0.1:9000')
            for case in plan.cases:
                with self.subTest(example=index, case=case.title):
                    self.assertEqual(case.source_ids, [])
                    self.assertIsNone(case.origin_case_id)
                    source = invoke_browser('compile', {
                        'baseUrl': 'http://127.0.0.1:9000', 'title': case.title,
                        'automation': case.automation.model_dump(exclude_none=True),
                    })['source']
                    self.assertIn('@playwright/test', source)
                    self.assertIn('.toHaveCount(1,', source)
                    self.assertIn('await expect(', source)


if __name__ == '__main__':
    unittest.main()

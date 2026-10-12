import unittest

from pydantic import ValidationError

from testagent.readiness import case_readiness
from testagent.schemas import AgentAnalysis, AgentFinding, GeneratedPlan, TestCaseDraft
from testagent.ui_agent import BrowserDecision


class ModelContractTests(unittest.TestCase):
    def test_unknown_commands_cannot_be_silently_ignored_in_model_responses(self):
        responses = [
            (AgentAnalysis, {'summary': 'Analysis of supplied evidence.', 'commands': ['delete']}),
            (AgentFinding, {'title': 'A finding', 'detail': 'A supplied observation.', 'action': 'run'}),
            (BrowserDecision, {'summary': 'Observe the page.', 'spawn_agents': ['security']}),
            (GeneratedPlan, {'intent': 'test_generation', 'summary': 'A plan',
                             'cases': [self.draft()], 'execute': True}),
            (TestCaseDraft, {**self.draft(), 'shell_command': 'run anything'}),
        ]
        for schema, payload in responses:
            with self.subTest(schema=schema.__name__):
                with self.assertRaises(ValidationError):
                    schema.model_validate(payload)

    @staticmethod
    def draft():
        return {'title': 'Health returns success', 'level': 'api', 'type': 'positive',
                'priority': 'medium', 'steps': ['Request health.'], 'expected': ['HTTP 200.']}

    def test_multiple_execution_payloads_are_rejected_before_storage(self):
        automation = {'actions': [{'action': 'navigate', 'url': '/'},
                                  {'action': 'assert_url', 'url': '/'}]}
        request = {'method': 'GET', 'path': '/health', 'expected_status': 200}
        for payload in ({'automation': automation, 'api_request': request},
                        {'automation': automation, 'unit_test_code': 'assert True'},
                        {'api_request': request, 'unit_test_code': 'assert True'}):
            with self.subTest(engines=list(payload)):
                with self.assertRaisesRegex(ValidationError, 'only one execution engine'):
                    TestCaseDraft.model_validate({**self.draft(), **payload})

    def test_existing_ambiguous_cases_cannot_enter_execution(self):
        payload = {'automation': {'actions': [{'action': 'navigate', 'url': '/'}]},
                   'api_request': {'method': 'GET', 'path': '/health', 'expected_status': 200}}
        self.assertEqual(case_readiness(payload, 'http://localhost')['status'], 'invalid')


if __name__ == '__main__':
    unittest.main()

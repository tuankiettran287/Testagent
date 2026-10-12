"""One named workflow check per role/helper, with real isolated HTTP/Chromium."""
import unittest

from scripts.verify_agents import AgentChecks
from testagent.browser_bridge import browser_runner_available
from testagent.skills import SKILLS


class SkillWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not browser_runner_available():
            raise unittest.SkipTest('Build browser_runner and install Chromium')
        cls.fixture = AgentChecks()
        cls.fixture.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.fixture.__exit__(None, None, None)


def role_test(skill_id):
    def test(self):
        self.assertEqual(self.fixture.check_role(skill_id)['status'], 'PASS')
    return test


def helper_test(skill_id):
    def test(self):
        result = self.fixture.check_helpers([skill_id])
        self.assertEqual(result[0]['function'], skill_id)
        self.assertEqual(result[0]['status'], 'PASS')
    return test


for skill in SKILLS:
    setattr(SkillWorkflowTests, 'test_skill_' + skill.id, role_test(skill.id))
    if skill.mode == 'analysis':
        setattr(SkillWorkflowTests, 'test_sub_agent_' + skill.id, helper_test(skill.id))


if __name__ == '__main__':
    unittest.main()

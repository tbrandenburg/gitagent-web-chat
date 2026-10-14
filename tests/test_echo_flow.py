"""Validate the bundled SkillsFlow demonstration without any model API calls."""

from pathlib import Path
import unittest

import yaml

BASE = Path(__file__).resolve().parents[1]
FLOW = BASE / "workflows" / "echo-chain.yaml"
SKILLS = ("echo-start", "echo-middle", "echo-end")
LABELS = ("ECHO_START:", "ECHO_MIDDLE:", "ECHO_END:")


class EchoFlowTests(unittest.TestCase):
    def test_flow_uses_supported_sequential_gitagent_schema(self):
        flow = yaml.safe_load(FLOW.read_text())
        self.assertEqual(flow["name"], "echo-chain")
        self.assertTrue(flow["description"])
        self.assertEqual([step["skill"] for step in flow["steps"]], list(SKILLS))
        for step in flow["steps"]:
            self.assertEqual(set(step), {"skill", "prompt"})
            self.assertTrue(step["prompt"].strip())

    def test_flow_passes_input_then_prior_step_results(self):
        steps = yaml.safe_load(FLOW.read_text())["steps"]
        self.assertIn("{input}", steps[0]["prompt"])
        self.assertIn("INPUT:", steps[0]["prompt"])
        self.assertNotIn("{input}", steps[1]["prompt"])
        self.assertIn("[Step 1 result (echo-start)]", steps[1]["prompt"])
        self.assertIn("[Step 2 result (echo-middle)]", steps[2]["prompt"])

    def test_each_step_has_matching_skill_definition(self):
        for name, label in zip(SKILLS, LABELS):
            with self.subTest(skill=name):
                skill_file = BASE / "skills" / name / "SKILL.md"
                raw = skill_file.read_text()
                self.assertTrue(raw.startswith("---\n"))
                frontmatter = yaml.safe_load(raw.split("---", 2)[1])
                self.assertEqual(frontmatter["name"], name)
                self.assertTrue(frontmatter["description"])
                self.assertIn(label, raw)
                self.assertIn("Do not call tools", raw)


if __name__ == "__main__":
    unittest.main()

from unittest import TestCase
from app.mission_plan import choose_agents, bounded_context, build_prompt


class MissionPlanTests(TestCase):
    def test_plain_request_does_not_match_ui_inside_quiero(self):
        self.assertEqual(choose_agents('Quiero investigar el proyecto'),['scout'])

    def test_hat_write_request_always_reaches_implementer_and_review(self):
        self.assertEqual(choose_agents('Quiero que al director le pongas un sombrero','workspace-write'),['muse','forge','sentinel'])

    def test_write_permission_handles_unanticipated_wording(self):
        selected=choose_agents('Hazlo como te dije','workspace-write')
        self.assertIn('forge',selected); self.assertIn('sentinel',selected)

    def test_guided_mode_adds_coordination_without_changing_specialists(self):
        efficient=choose_agents('Investiga el proyecto')
        guided=choose_agents('Investiga el proyecto',planning='guided')
        self.assertEqual(guided,['director','nexus',*efficient])

    def test_context_is_bounded_and_keeps_recent_contributions(self):
        context=bounded_context(['old'*1000,'next'*1000,'useful'*1000,'latest'*1000])
        self.assertLessEqual(len(context),6000); self.assertNotIn('old',context); self.assertIn('latest',context)

    def test_prompt_keeps_goal_and_profile_without_unbounded_predecessors(self):
        step={'agent_id':'forge','name':'FORGE','token_budget':7000}
        prompt=build_prompt({'prompt':'Put a hat on DIRECTOR'},step,['x'*100000]*10)
        self.assertIn('Put a hat on DIRECTOR',prompt); self.assertIn('FORGE',prompt)
        self.assertLess(len(prompt),10000)

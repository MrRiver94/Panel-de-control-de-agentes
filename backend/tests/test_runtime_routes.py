from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from fastapi.testclient import TestClient
from app import state
from app.main import app
from app.execution_store import save_execution, save_execution_diffs


class RuntimeRouteTests(TestCase):
    def setUp(self):
        self.directory=TemporaryDirectory(); self.addCleanup(self.directory.cleanup)
        original={key:value.model_copy(deep=True) for key,value in state.agents.items()}
        self.addCleanup(lambda:(state.agents.clear(),state.agents.update(original)))
        db=patch.object(state,'AUDIT_DATABASE',Path(self.directory.name)/'test.sqlite3'); db.start(); self.addCleanup(db.stop)
        monitor=patch('app.external_monitor.get_codex_sessions',return_value={'sessions':[]}); monitor.start(); self.addCleanup(monitor.stop)
        self.client=TestClient(app,base_url='http://127.0.0.1',client=('127.0.0.1',60001),headers={'X-Operator-Id':'super-admin'})
        self.client.__enter__(); self.addCleanup(lambda:self.client.__exit__(None,None,None))

    def test_browser_from_remote_origin_cannot_launch_a_mission(self):
        with patch('app.routes.missions.manager.start') as start:
            response=self.client.post('/api/dispatch',json={'prompt':'Modify app'},headers={'Origin':'https://remote.example'})
        self.assertEqual(response.status_code,403); start.assert_not_called()

    def test_local_mission_acceptance_and_role_denial(self):
        accepted={'execution_id':'fake','agent_ids':['forge'],'plan':'fixture'}
        with patch('app.routes.missions.manager.start',return_value=accepted) as start:
            self.assertEqual(self.client.post('/api/dispatch',json={'prompt':'Modify app'}).status_code,202)
            self.assertEqual(self.client.post('/api/dispatch',json={'prompt':'Modify app'},headers={'X-Operator-Id':'unknown'}).status_code,403)
            self.assertEqual(start.call_count,1)

    def test_retry_keeps_original_history_and_only_retries_allowed_states(self):
        original={'id':'old','created_at':'now','status':'cancelled','prompt':'Modify app','workspace':self.directory.name,'sandbox':'workspace-write','steps':[]}
        save_execution(original)
        with patch('app.routes.missions.manager.start',return_value={'execution_id':'new','agent_ids':['forge'],'plan':'fixture'}):
            self.assertEqual(self.client.post('/api/executions/old/retry').status_code,202)
        original['status']='completed'; save_execution(original)
        self.assertEqual(self.client.post('/api/executions/old/retry').status_code,409)
        self.assertEqual(self.client.post('/api/executions/missing/retry').status_code,404)

    def test_diff_is_persistent_and_access_checked(self):
        save_execution({'id':'diff','created_at':'now','status':'completed','steps':[]})
        save_execution_diffs('diff',[{'path':'app.js','patch':'-old\n+new'}])
        self.assertIn('+new',self.client.get('/api/executions/diff/diff').json()['files'][0]['patch'])
        self.assertEqual(self.client.get('/api/executions/diff/diff',headers={'X-Operator-Id':'unknown'}).status_code,403)
        self.assertEqual(self.client.get('/api/executions/missing/diff').status_code,404)

    def test_session_binding_persists_and_operator_cannot_change_it(self):
        body={'session_id':'test-session','agent_id':'scout'}
        self.assertEqual(self.client.post('/api/session-bindings',json=body).status_code,200)
        self.assertEqual(self.client.post('/api/session-bindings',json=body,headers={'X-Operator-Id':'operador-misiones'}).status_code,403)
        body['agent_id']='missing'
        self.assertEqual(self.client.post('/api/session-bindings',json=body).status_code,400)

    def test_summary_does_not_download_all_phase_results(self):
        save_execution({'id':'large','created_at':'now','status':'completed','steps':[{'agent_id':'scout','result':'x'*10000,'review':{'summary':'long'}}]})
        full=self.client.get('/api/executions')
        summary=self.client.get('/api/executions?summary=true')
        self.assertLess(len(summary.content),len(full.content)//2)
        self.assertNotIn('result',summary.json()[0]['steps'][0])
        self.assertTrue(summary.json()[0]['steps'][0]['has_result'])

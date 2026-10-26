"""Lifecycle regressions with a fake transport; never invoke a model."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
import subprocess
import threading
import json

from fastapi import HTTPException
from app import state
from app.execution import ExecutionManager
from app.execution_store import create_execution_schema, read_execution, read_executions
from app.models import DispatchRequest
from app.repository import create_audit_schema


class ExecutionTests(TestCase):
    def setUp(self):
        logger=patch('app.execution.LOGGER'); logger.start(); self.addCleanup(logger.stop)
        self.directory = TemporaryDirectory(); self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.workspace = self.root/'project'; self.workspace.mkdir()
        subprocess.run(['git','init','-q',str(self.workspace)], check=True, capture_output=True)
        (self.workspace/'app.txt').write_text('original',encoding='utf-8')
        original = {key:agent.model_copy(deep=True) for key,agent in state.agents.items()}
        self.addCleanup(lambda: (state.agents.clear(),state.agents.update(original)))
        db = patch.object(state,'AUDIT_DATABASE',self.root/'test.sqlite3'); db.start(); self.addCleanup(db.stop)
        for agent in state.agents.values(): agent.provider='codex'
        create_audit_schema(); create_execution_schema()
        self.manager=ExecutionManager(); self.addCleanup(self.manager.shutdown)
        for target,value in [('app.execution.find_codex','codex'),('app.execution.login_ready',(True,'ready'))]:
            p=patch(target,return_value=value); p.start(); self.addCleanup(p.stop)

    def request(self, mode='read-only', request_id=None):
        return DispatchRequest(prompt='Investiga el proyecto',workspace=str(self.workspace),sandbox=mode,request_id=request_id,planning='guided')

    def finish(self, result):
        self.manager.worker.join(5)
        self.assertFalse(self.manager.worker.is_alive())
        return read_execution(result['execution_id'])

    @staticmethod
    def fake(args,prompt,workspace,cancelled,event,on_process):
        event({'type':'thread.started','thread_id':'fixture-session'})
        event({'type':'turn.started'})
        event({'type':'item.completed','item':{'type':'agent_message','text':'Fixture result'}})
        event({'type':'turn.completed','usage':{'input_tokens':100,'output_tokens':7,'reasoning_output_tokens':3,'cached_input_tokens':80}})

    def test_completed_turn_records_usage_without_double_counting(self):
        with patch('app.execution.run_codex',side_effect=self.fake):
            result=self.finish(self.manager.start(self.request()))
        self.assertEqual(result['status'],'completed')
        self.assertEqual(result['steps'][0]['usage']['output_tokens'],7)
        self.assertEqual(state.agents['director'].tokens_used,107)
        self.assertTrue(all(step['status']=='completed' for step in result['steps']))

    def test_missing_completion_and_failure_do_not_report_success(self):
        with patch('app.execution.run_codex',return_value=None):
            result=self.finish(self.manager.start(self.request()))
        self.assertEqual(result['status'],'failed')
        self.assertEqual(result['steps'][1]['status'],'skipped')

    def test_write_mission_without_edits_is_no_changes(self):
        with patch('app.execution.run_codex',side_effect=self.fake):
            result=self.finish(self.manager.start(self.request('workspace-write')))
        self.assertEqual(result['status'],'no_changes')
        self.assertIn('forge',[step['agent_id'] for step in result['steps']])

    def test_edits_are_recorded_even_when_transport_fails(self):
        def failing(args,*rest):
            if 'workspace-write' in args:
                (self.workspace/'app.txt').write_text('changed',encoding='utf-8')
                raise RuntimeError('fixture failure')
            self.fake(args,*rest)
        with patch('app.execution.run_codex',side_effect=failing):
            result=self.finish(self.manager.start(self.request('workspace-write')))
        self.assertEqual(result['status'],'failed')
        self.assertEqual(result['changed_files'],['app.txt'])

    def test_duplicate_request_returns_same_execution_and_rejects_changed_payload(self):
        with patch('app.execution.run_codex',side_effect=self.fake):
            first=self.manager.start(self.request(request_id='same-request'))
            self.finish(first)
            second=self.manager.start(self.request(request_id='same-request'))
            self.assertEqual(first['execution_id'],second['execution_id'])
            with self.assertRaises(HTTPException) as error:
                self.manager.start(self.request('workspace-write','same-request'))
            self.assertEqual(error.exception.status_code,409)
        self.assertEqual(len(read_executions()),1)

    def test_cancel_stops_pipeline_and_rejects_concurrent_mission(self):
        entered=threading.Event()
        def pending(args,prompt,workspace,cancelled,*rest):
            entered.set(); cancelled.wait(3)
            raise InterruptedError()
        with patch('app.execution.run_codex',side_effect=pending):
            first=self.manager.start(self.request())
            self.assertTrue(entered.wait(2))
            with self.assertRaises(HTTPException) as error: self.manager.start(self.request())
            self.assertEqual(error.exception.status_code,409)
            self.manager.cancel(first['execution_id'])
            result=self.finish(first)
        self.assertEqual(result['status'],'cancelled')
        self.assertFalse(any(step['status']=='running' for step in result['steps']))

    def test_restart_marks_unfinished_mission_interrupted_without_replay(self):
        from app.execution_store import save_execution
        save_execution({'id':'old','status':'running','created_at':'now','active_agent':'forge',
                        'steps':[{'agent_id':'forge','status':'running','usage':None},{'agent_id':'sentinel','status':'queued','usage':None}]})
        self.manager.recover()
        result=read_execution('old')
        self.assertEqual(result['status'],'interrupted')
        self.assertEqual(result['steps'][1]['status'],'skipped')
        self.assertIsNone(self.manager.worker)

    def run_write_review(self, verdict):
        def transport(args,prompt,workspace,cancelled,event,on_process):
            if 'workspace-write' in args:
                (self.workspace/'app.txt').write_text('implemented',encoding='utf-8')
            result=json.dumps({'verdict':verdict,'summary':'fixture review','findings':[]}) if '--output-schema' in args else 'implemented'
            event({'type':'item.completed','item':{'type':'agent_message','text':result}})
            event({'type':'turn.completed','usage':{'input_tokens':10,'output_tokens':2}})
        request=DispatchRequest(prompt='Cambia app.txt',workspace=str(self.workspace),sandbox='workspace-write')
        with patch('app.execution.run_codex',side_effect=transport):
            return self.finish(self.manager.start(request))

    def test_verified_write_and_diff_finish_with_approval(self):
        from app.execution_store import read_execution_diffs
        result=self.run_write_review('approved')
        self.assertEqual(result['status'],'completed')
        self.assertEqual(result['steps'][-1]['review']['verdict'],'approved')
        self.assertIn('+implemented',read_execution_diffs(result['id'])[0]['patch'])

    def test_review_with_observations_is_not_reported_as_fully_completed(self):
        result=self.run_write_review('changes_requested')
        self.assertEqual(result['status'],'needs_review')

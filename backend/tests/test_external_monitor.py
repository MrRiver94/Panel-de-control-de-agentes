"""Local event fixtures; no calls to Codex or user session contents."""
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
import json

from app import state
from app.rollout_reader import read_session, _files
from app.external_monitor import project_external_agents, external_sessions
from app.repository import create_audit_schema
from app.execution_store import create_execution_schema, save_execution


class RolloutTests(TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'rollout-test.jsonl'
        _files.clear()

    def write(self, *records):
        self.path.write_text('\n'.join(json.dumps(record) for record in records) + '\n', encoding='utf-8')
        return read_session(self.path, self.path.stat().st_mtime)

    def test_explicit_lifecycle_drives_state_and_no_private_text_is_returned(self):
        result = self.write(
            {'type':'session_meta','payload':{'id':'one','cwd':self.directory.name,'source':'vscode'}},
            {'type':'event_msg','payload':{'type':'task_started'}},
            {'type':'response_item','payload':{'type':'reasoning','text':'PRIVATE'}},
            {'type':'token_usage_record','payload':{'turn_token_usage':{'input_tokens':20,'output_tokens':5,'reasoning_output_tokens':2}}},
        )
        self.assertEqual(result['operational_status'], 'thinking')
        self.assertEqual(result['turn_usage']['total_tokens'], 25)
        self.assertNotIn('PRIVATE', json.dumps(result))
        with self.path.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps({'type':'event_msg','payload':{'type':'task_complete'}})+'\n')
        self.assertEqual(read_session(self.path, self.path.stat().st_mtime)['operational_status'], 'standby')

    def test_cached_active_session_becomes_stale_without_a_new_file_write(self):
        self.write({'type':'event_msg','payload':{'type':'task_started'}})
        mtime = self.path.stat().st_mtime
        result = read_session(self.path, mtime, now=mtime+181)
        self.assertTrue(result['signal_stale'])
        self.assertEqual(result['operational_status'], 'standby')

    def test_large_rollout_keeps_header_and_ignores_malformed_records(self):
        header = {'type':'session_meta','payload':{'id':'big','cwd':self.directory.name,'source':'vscode'}}
        self.path.write_text(json.dumps(header)+'\n'+json.dumps({'padding':'x'*2000})+'\n'+
                             '[]\n{"payload":"wrong"}\n'+json.dumps({'type':'event_msg','payload':{'type':'task_complete'}})+'\n{partial',encoding='utf-8')
        with patch('app.rollout_reader.TAIL_BYTES',300):
            result = read_session(self.path,self.path.stat().st_mtime)
        self.assertEqual(result['id'],'big')
        self.assertEqual(result['workspace'],self.directory.name)
        self.assertEqual(result['operational_status'],'standby')

    def test_abort_does_not_leave_an_agent_running(self):
        result = self.write({'type':'event_msg','payload':{'type':'task_started'}}, {'type':'event_msg','payload':{'type':'turn_aborted'}})
        self.assertEqual(result['operational_status'],'standby')


class ExternalProjectionTests(TestCase):
    def setUp(self):
        self.directory=TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        database=patch.object(state,'AUDIT_DATABASE',Path(self.directory.name)/'test.sqlite3')
        database.start(); self.addCleanup(database.stop)
        create_audit_schema(); create_execution_schema()
        self.session={'id':'external','workspace':self.directory.name,'source':'vscode','operational_status':'thinking','signal_stale':False,'work_action':'thinking','turn_usage':{'total_tokens':100},'updated_at':'2026-10-24T12:00:00Z','status':'activa'}

    def test_only_one_representative_moves_and_managed_owner_has_priority(self):
        sessions=[{**self.session,'agent_id':'forge'}]
        agents=[agent.model_dump() for agent in state.agents.values()]
        for agent in agents: agent.update(status='standby',execution_id=None)
        result=project_external_agents(agents,sessions)
        self.assertEqual([agent['id'] for agent in result if agent['status']=='thinking'],['forge'])
        forge=next(agent for agent in agents if agent['id']=='forge')
        forge.update(execution_id='managed',status='running')
        self.assertEqual(next(agent for agent in project_external_agents(agents,sessions) if agent['id']=='forge')['usage_source'],'codex-exec')

    def test_project_filter_ignores_internal_and_managed_sessions_and_similar_paths(self):
        save_execution({'id':'run','created_at':'now','steps':[{'session_id':'managed'}]})
        sessions=[self.session,{**self.session,'id':'managed'},{**self.session,'id':'guardian','source':'internal'},
                  {**self.session,'id':'other','workspace':self.directory.name+'-different'}]
        with patch('app.external_monitor.get_codex_sessions',return_value={'sessions':sessions}):
            result=external_sessions(self.directory.name)
        self.assertEqual([session['id'] for session in result],['external'])
        self.assertEqual(result[0]['agent_id'],'forge')


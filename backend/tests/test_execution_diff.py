from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
import subprocess
import os

from app.execution_diff import capture_baseline, collect_diffs
from app.git_local import run_git
from types import SimpleNamespace


class DiffTests(TestCase):
    def setUp(self):
        self.directory=TemporaryDirectory(); self.addCleanup(self.directory.cleanup)
        self.root=Path(self.directory.name)
        self.git('init','-q')

    def git(self,*args):
        return subprocess.run(['git','-C',str(self.root),*args],capture_output=True,check=True).stdout

    def test_existing_dirty_file_diff_begins_at_pre_mission_content(self):
        file=self.root/'app.txt'; file.write_text('index\n',encoding='utf-8'); self.git('add','app.txt')
        file.write_text('user changes\n',encoding='utf-8')
        baseline=capture_baseline(str(self.root))
        file.write_text('mission changes\n',encoding='utf-8')
        result=collect_diffs(str(self.root),baseline)
        self.assertIn('-user changes',result[0]['patch']); self.assertNotIn('-index',result[0]['patch'])

    def test_new_deleted_and_originally_clean_files(self):
        (self.root/'clean.txt').write_text('old',encoding='utf-8'); self.git('add','clean.txt')
        baseline=capture_baseline(str(self.root))
        (self.root/'clean.txt').unlink()
        (self.root/'new.txt').write_text('new',encoding='utf-8')
        result={item['path']:item for item in collect_diffs(str(self.root),baseline)}
        self.assertIn('-old',result['clean.txt']['patch']); self.assertIn('+new',result['new.txt']['patch'])

    def test_unrelated_preexisting_changes_are_not_attributed_to_mission(self):
        (self.root/'user.txt').write_text('untouched',encoding='utf-8')
        baseline=capture_baseline(str(self.root))
        self.assertEqual(collect_diffs(str(self.root),baseline),[])

    def test_binary_large_and_sensitive_paths_are_not_exposed(self):
        baseline=capture_baseline(str(self.root))
        (self.root/'image.bin').write_bytes(b'\0\xff')
        (self.root/'big.txt').write_text('x'*129000)
        (self.root/'.env').write_text('TOP_SECRET')
        result={item['path']:item for item in collect_diffs(str(self.root),baseline)}
        self.assertTrue(result['image.bin']['binary']); self.assertTrue(result['big.txt']['binary'])
        self.assertTrue(result['.env']['redacted']); self.assertNotIn('TOP_SECRET',result['.env']['patch'])

    def test_secret_values_are_redacted_and_patch_is_bounded(self):
        baseline=capture_baseline(str(self.root))
        (self.root/'config.txt').write_text('api_key="private-value"\n'+'long\n'*500,encoding='utf-8')
        with patch('app.execution_diff.MAX_PATCH_CHARS',200): result=collect_diffs(str(self.root),baseline)[0]
        self.assertTrue(result['redacted']); self.assertTrue(result['truncated'])
        self.assertNotIn('private-value',result['patch']); self.assertLessEqual(len(result['patch']),200)

    def test_nested_workspace_reads_correct_index_blobs(self):
        nested=self.root/'src'; nested.mkdir()
        file=nested/'app.txt'; file.write_text('before\n',encoding='utf-8'); self.git('add','src/app.txt')
        baseline=capture_baseline(str(nested)); file.write_text('after\n',encoding='utf-8')
        result=collect_diffs(str(nested),baseline)
        self.assertEqual(result[0]['path'],'app.txt'); self.assertIn('-before',result[0]['patch'])

    def test_git_operations_do_not_inherit_another_repository(self):
        with patch.dict(os.environ,{'GIT_DIR':str(self.root/'missing-repository'),'GIT_INDEX_FILE':str(self.root/'bad-index')}):
            baseline=capture_baseline(str(self.root))
            (self.root/'new.txt').write_text('selected project',encoding='utf-8')
            self.assertEqual(collect_diffs(str(self.root),baseline)[0]['path'],'new.txt')

    def test_git_ownership_rejection_is_explained_without_disabling_protection(self):
        failure=SimpleNamespace(returncode=128,stderr=b'fatal: detected dubious ownership in repository',stdout=b'')
        with patch('app.git_local.subprocess.run',return_value=failure) as command, self.assertLogs('app.git_local',level='ERROR'):
            with self.assertRaisesRegex(RuntimeError,'propietario'):
                run_git(str(self.root),'status')
            self.assertEqual(command.call_count,1)
            self.assertNotIn('--global',command.call_args.args[0])

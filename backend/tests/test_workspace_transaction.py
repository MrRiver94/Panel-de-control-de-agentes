"""Publication and containment tests use disposable Git repositories only."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
import os
import subprocess

from app.git_local import git_environment
from app.execution_diff import capture_baseline, collect_diffs
from app.workspace_transaction import WorkspaceTransaction, WorkspaceConflictError, WorkspaceTransactionError


class WorkspaceTransactionTests(TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        self.storage = self.root / 'transactions'
        self.git('init', '-q')
        self.git('config', 'user.name', 'Fixture')
        self.git('config', 'user.email', 'fixture@localhost')
        self.git('config', 'core.autocrlf', 'false')

    def git(self, *arguments):
        return subprocess.run(['git', '-C', str(self.source), *arguments], check=True, capture_output=True,
                              env=git_environment(), creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0).stdout

    def write(self, name, content):
        path = self.source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
        return path

    def commit(self):
        self.git('add', '--all')
        self.git('-c', 'commit.gpgsign=false', 'commit', '--allow-empty', '-qm', 'Fixture')

    def transaction(self):
        return WorkspaceTransaction(self.source, self.storage)

    def test_dirty_staged_untracked_deleted_and_ignored_baseline_is_preserved(self):
        self.write('dirty.txt', 'committed')
        deleted = self.write('deleted.txt', 'deleted baseline')
        self.write('.gitignore', 'dependencies/\n.env\n')
        self.commit()
        self.write('dirty.txt', 'staged')
        self.git('add', 'dirty.txt')
        self.write('dirty.txt', 'working tree')
        self.write('untracked.txt', 'user work')
        self.write('dependencies/large.txt', 'ignored dependency')
        self.write('.env', 'PRIVATE_FIXTURE')
        deleted.unlink()
        index = self.git('ls-files', '--stage', '-z')
        status = self.git('status', '--porcelain=v1', '-z')
        transaction = self.transaction()
        sandbox = Path(transaction.prepare())
        self.assertEqual((sandbox / 'dirty.txt').read_text(), 'working tree')
        self.assertEqual((sandbox / 'untracked.txt').read_text(), 'user work')
        self.assertFalse((sandbox / 'deleted.txt').exists())
        self.assertFalse((sandbox / 'dependencies').exists())
        self.assertFalse((sandbox / '.env').exists())
        self.assertEqual(transaction.publish(), [])
        self.assertEqual(self.git('ls-files', '--stage', '-z'), index)
        self.assertEqual(self.git('status', '--porcelain=v1', '-z'), status)
        transaction.cleanup()
        self.assertIsNone(transaction.recovery_path)

    def test_publish_applies_only_mission_add_update_delete_and_keeps_original_git(self):
        self.write('update.txt', 'old')
        self.write('delete.txt', 'remove')
        self.write('unrelated.txt', 'user baseline')
        self.commit()
        self.write('unrelated.txt', 'existing dirty work')
        self.write('untracked.txt', 'existing untracked work')
        index = self.git('ls-files', '--stage', '-z')
        head = self.git('rev-parse', 'HEAD')
        transaction = self.transaction()
        sandbox = Path(transaction.prepare())
        (sandbox / 'update.txt').write_text('mission update')
        (sandbox / 'delete.txt').unlink()
        (sandbox / 'new').mkdir()
        (sandbox / 'new' / 'added.txt').write_text('mission addition')
        self.assertEqual(transaction.publish(), ['delete.txt', 'new/added.txt', 'update.txt'])
        self.assertEqual((self.source / 'update.txt').read_text(), 'mission update')
        self.assertEqual((self.source / 'new' / 'added.txt').read_text(), 'mission addition')
        self.assertFalse((self.source / 'delete.txt').exists())
        self.assertEqual((self.source / 'unrelated.txt').read_text(), 'existing dirty work')
        self.assertEqual((self.source / 'untracked.txt').read_text(), 'existing untracked work')
        self.assertEqual(self.git('ls-files', '--stage', '-z'), index)
        self.assertEqual(self.git('rev-parse', 'HEAD'), head)
        self.assertEqual(transaction.publish(), ['delete.txt', 'new/added.txt', 'update.txt'])
        transaction.cleanup()

    def test_external_edit_of_unrelated_file_rejects_all_mission_changes(self):
        self.write('a.txt', 'a baseline')
        self.write('b.txt', 'b baseline')
        self.commit()
        transaction = self.transaction()
        sandbox = Path(transaction.prepare())
        (sandbox / 'a.txt').write_text('mission')
        (sandbox / 'new.txt').write_text('addition')
        self.write('b.txt', 'external edit')
        with self.assertRaises(WorkspaceConflictError):
            transaction.publish()
        self.assertEqual((self.source / 'a.txt').read_text(), 'a baseline')
        self.assertEqual((self.source / 'b.txt').read_text(), 'external edit')
        self.assertFalse((self.source / 'new.txt').exists())
        transaction.cleanup()
        self.assertTrue(Path(transaction.recovery_path).is_dir())

    def test_new_external_untracked_file_also_rejects_publication(self):
        self.write('a.txt', 'baseline')
        self.commit()
        transaction = self.transaction()
        sandbox = Path(transaction.prepare())
        (sandbox / 'a.txt').write_text('mission')
        self.write('external.txt', 'external addition')
        with self.assertRaises(WorkspaceConflictError):
            transaction.publish()
        self.assertEqual((self.source / 'a.txt').read_text(), 'baseline')

    def test_index_or_head_changes_are_conflicts_even_if_contents_match(self):
        self.write('a.txt', 'baseline')
        self.commit()
        self.write('a.txt', 'dirty')
        transaction = self.transaction()
        sandbox = Path(transaction.prepare())
        (sandbox / 'a.txt').write_text('mission')
        self.git('add', 'a.txt')
        with self.assertRaises(WorkspaceConflictError):
            transaction.publish()
        self.assertEqual((self.source / 'a.txt').read_text(), 'dirty')

    def test_head_only_change_is_a_conflict(self):
        self.write('a.txt', 'baseline')
        self.commit()
        transaction = self.transaction()
        sandbox = Path(transaction.prepare())
        (sandbox / 'a.txt').write_text('mission')
        self.git('-c', 'commit.gpgsign=false', 'commit', '--allow-empty', '-qm', 'External commit')
        with self.assertRaises(WorkspaceConflictError):
            transaction.publish()
        self.assertEqual((self.source / 'a.txt').read_text(), 'baseline')

    def test_external_edit_during_staging_is_detected_before_any_replacement(self):
        self.write('a.txt', 'a baseline')
        self.write('b.txt', 'b baseline')
        self.commit()
        transaction = self.transaction()
        sandbox = Path(transaction.prepare())
        (sandbox / 'a.txt').write_text('mission')
        import shutil
        real_copy = shutil.copy2

        def copy_and_edit(source, target):
            result = real_copy(source, target)
            if Path(source) == sandbox / 'a.txt':
                self.write('b.txt', 'external edit during staging')
            return result

        with patch('app.workspace_transaction.shutil.copy2', side_effect=copy_and_edit), self.assertRaises(WorkspaceConflictError):
            transaction.publish()
        self.assertEqual((self.source / 'a.txt').read_text(), 'a baseline')
        self.assertEqual((self.source / 'b.txt').read_text(), 'external edit during staging')
        self.assertFalse(list(self.source.glob('.slimeops-*.tmp')))

    def test_external_edit_during_replacement_rolls_back_mission_delta(self):
        self.write('a.txt', 'a baseline')
        self.write('b.txt', 'b baseline')
        self.commit()
        transaction = self.transaction()
        sandbox = Path(transaction.prepare())
        (sandbox / 'a.txt').write_text('mission')
        real_replace = os.replace
        edited = False

        def replace_and_edit(source, target):
            nonlocal edited
            result = real_replace(source, target)
            if not edited:
                edited = True
                self.write('b.txt', 'external edit during publication')
            return result

        with patch('app.workspace_transaction.os.replace', side_effect=replace_and_edit), self.assertRaises(WorkspaceConflictError):
            transaction.publish()
        self.assertEqual((self.source / 'a.txt').read_text(), 'a baseline')
        self.assertEqual((self.source / 'b.txt').read_text(), 'external edit during publication')

    def test_changing_ignore_rules_keeps_preexisting_untracked_content(self):
        self.write('.gitignore', '')
        self.commit()
        self.write('user.txt', 'preexisting untracked work')
        transaction = self.transaction()
        sandbox = Path(transaction.prepare())
        (sandbox / '.gitignore').write_text('user.txt\n')
        self.assertEqual(transaction.publish(), ['.gitignore'])
        self.assertEqual((self.source / 'user.txt').read_text(), 'preexisting untracked work')

    def test_new_file_cannot_overwrite_an_ignored_original(self):
        self.write('.gitignore', 'private.txt\n')
        self.commit()
        self.write('private.txt', 'original private content')
        transaction = self.transaction()
        sandbox = Path(transaction.prepare())
        (sandbox / '.gitignore').write_text('')
        (sandbox / 'private.txt').write_text('mission collision')
        with self.assertRaises(WorkspaceConflictError):
            transaction.publish()
        self.assertEqual((self.source / 'private.txt').read_text(), 'original private content')
        self.assertEqual((self.source / '.gitignore').read_text(), 'private.txt\n')

    def test_empty_unborn_repository_is_supported(self):
        transaction = self.transaction()
        sandbox = Path(transaction.prepare())
        (sandbox / 'new.txt').write_text('new file')
        self.assertEqual(transaction.publish(), ['new.txt'])
        self.assertEqual((self.source / 'new.txt').read_text(), 'new file')
        self.assertEqual(self.git('ls-files'), b'')

    def test_nested_workspace_keeps_changes_inside_selected_directory(self):
        self.write('src/a.txt', 'selected')
        self.write('outside.txt', 'unrelated')
        self.commit()
        transaction = WorkspaceTransaction(self.source / 'src', self.storage)
        sandbox = Path(transaction.prepare())
        self.assertFalse((sandbox / 'outside.txt').exists())
        self.assertEqual((sandbox.parent / 'outside.txt').read_text(), 'unrelated')
        (sandbox / 'a.txt').write_text('mission')
        self.assertEqual(transaction.publish(), ['a.txt'])
        self.assertEqual((self.source / 'outside.txt').read_text(), 'unrelated')

    def test_nested_workspace_preserves_parent_and_info_exclude_rules_for_future_outputs(self):
        self.write('.gitignore', 'node_modules/\n.env\n')
        self.write('frontend/app.txt', 'baseline')
        self.write('package.json', '{"private": true}')
        self.commit()
        source_exclude = self.source / '.git' / 'info' / 'exclude'
        source_exclude.write_text('/frontend/private-cache/\n')
        self.write('frontend/node_modules/existing.txt', 'private ignored dependency')
        self.write('frontend/.env', 'PRIVATE_FIXTURE')
        transaction = WorkspaceTransaction(self.source / 'frontend', self.storage)
        sandbox = Path(transaction.prepare())
        self.assertEqual((sandbox.parent / 'package.json').read_text(), '{"private": true}')
        self.assertFalse((sandbox / 'node_modules').exists())
        self.assertFalse((sandbox / '.env').exists())
        before = capture_baseline(str(sandbox))
        (sandbox / 'node_modules').mkdir()
        (sandbox / 'node_modules' / 'new.txt').write_text('new ignored dependency')
        (sandbox / '.env').write_text('NEW_PRIVATE_FIXTURE')
        (sandbox / 'private-cache').mkdir()
        (sandbox / 'private-cache' / 'new.txt').write_text('ignored local cache')
        (sandbox / 'app.txt').write_text('mission')
        self.assertEqual([item['path'] for item in collect_diffs(str(sandbox), before)], ['app.txt'])
        self.assertEqual(transaction.publish(), ['app.txt'])
        self.assertEqual((self.source / 'frontend' / '.env').read_text(), 'PRIVATE_FIXTURE')
        self.assertFalse((self.source / 'frontend' / 'node_modules' / 'new.txt').exists())
        self.assertFalse((self.source / 'frontend' / 'private-cache').exists())
        self.assertEqual(source_exclude.read_text(), '/frontend/private-cache/\n')

    def test_ancestor_context_or_exclude_rules_changing_causes_conflict(self):
        self.write('.gitignore', 'node_modules/\n')
        self.write('frontend/app.txt', 'baseline')
        self.write('package.json', '{"private": true}')
        self.commit()
        transaction = WorkspaceTransaction(self.source / 'frontend', self.storage)
        sandbox = Path(transaction.prepare())
        (sandbox / 'app.txt').write_text('mission')
        self.write('package.json', '{"changed": true}')
        with self.assertRaises(WorkspaceConflictError):
            transaction.publish()
        self.assertEqual((self.source / 'frontend' / 'app.txt').read_text(), 'baseline')

        second = WorkspaceTransaction(self.source / 'frontend', self.storage)
        second_sandbox = Path(second.prepare())
        (second_sandbox / 'app.txt').write_text('second mission')
        (self.source / '.git' / 'info' / 'exclude').write_text('cache/\n')
        with self.assertRaises(WorkspaceConflictError):
            second.publish()
        self.assertEqual((self.source / 'frontend' / 'app.txt').read_text(), 'baseline')

    def test_local_absolute_excludes_are_frozen_and_hide_future_outputs(self):
        self.write('frontend/app.txt', 'baseline')
        self.commit()
        rules = self.root / 'private.ignore'
        rules.write_text('future-cache/\n.env\n')
        self.git('config', 'core.excludesFile', str(rules))
        self.write('frontend/.env', 'ORIGINAL_PRIVATE_FIXTURE')
        transaction = WorkspaceTransaction(self.source / 'frontend', self.storage)
        sandbox = Path(transaction.prepare())
        self.assertFalse((sandbox / '.env').exists())
        before = capture_baseline(str(sandbox))
        (sandbox / 'app.txt').write_text('mission')
        (sandbox / 'future-cache').mkdir()
        (sandbox / 'future-cache' / 'cache.txt').write_text('ignored output')
        (sandbox / '.env').write_text('NEW_PRIVATE_FIXTURE')
        self.assertEqual([item['path'] for item in collect_diffs(str(sandbox), before)], ['app.txt'])
        self.assertEqual(transaction.publish(), ['app.txt'])
        self.assertEqual((self.source / 'frontend' / '.env').read_text(), 'ORIGINAL_PRIVATE_FIXTURE')
        self.assertFalse((self.source / 'frontend' / 'future-cache').exists())
        self.assertEqual(self.git('config', '--path', '--get', 'core.excludesFile').decode().strip(), str(rules))

    def test_relative_excludes_use_repository_root_even_for_selected_subdirectory(self):
        self.write('rules.ignore', 'root-cache/\n.env\n')
        self.write('frontend/rules.ignore', 'wrong-cache/\n')
        self.write('frontend/app.txt', 'baseline')
        self.commit()
        self.git('config', 'core.excludesFile', 'rules.ignore')
        transaction = WorkspaceTransaction(self.source / 'frontend', self.storage)
        sandbox = Path(transaction.prepare())
        before = capture_baseline(str(sandbox))
        (sandbox / 'root-cache').mkdir()
        (sandbox / 'root-cache' / 'new.txt').write_text('ignored output')
        (sandbox / '.env').write_text('PRIVATE_FIXTURE')
        self.assertEqual(collect_diffs(str(sandbox), before), [])
        self.assertEqual(transaction.publish(), [])
        self.assertFalse((self.source / 'frontend' / 'root-cache').exists())
        self.assertFalse((self.source / 'frontend' / '.env').exists())

    def test_excludes_content_or_config_changes_are_conflicts(self):
        self.write('app.txt', 'baseline')
        self.commit()
        rules = self.root / 'private.ignore'
        rules.write_text('future-cache/\n')
        self.git('config', 'core.excludesFile', str(rules))
        transaction = self.transaction()
        sandbox = Path(transaction.prepare())
        (sandbox / 'app.txt').write_text('mission')
        rules.write_text('changed-cache/\n')
        with self.assertRaises(WorkspaceConflictError):
            transaction.publish()
        self.assertEqual((self.source / 'app.txt').read_text(), 'baseline')
        second = self.transaction()
        second_sandbox = Path(second.prepare())
        (second_sandbox / 'app.txt').write_text('second mission')
        self.git('config', 'core.excludesFile', str(self.root / 'different.ignore'))
        with self.assertRaises(WorkspaceConflictError):
            second.publish()
        self.assertEqual((self.source / 'app.txt').read_text(), 'baseline')

    def test_missing_configured_excludes_is_empty_and_its_creation_is_a_conflict(self):
        self.write('app.txt', 'baseline')
        self.commit()
        missing = self.root / 'missing.ignore'
        self.git('config', 'core.excludesFile', str(missing))
        first = self.transaction()
        sandbox = Path(first.prepare())
        (sandbox / 'app.txt').write_text('mission')
        self.assertEqual(first.publish(), ['app.txt'])
        self.assertFalse(missing.exists())
        second = self.transaction()
        second_sandbox = Path(second.prepare())
        (second_sandbox / 'app.txt').write_text('second mission')
        missing.write_text('cache/\n')
        with self.assertRaises(WorkspaceConflictError):
            second.publish()
        self.assertEqual((self.source / 'app.txt').read_text(), 'mission')

    def test_source_submodules_are_rejected_explicitly(self):
        self.write('a.txt', 'baseline')
        self.commit()
        oid = self.git('rev-parse', 'HEAD').decode().strip()
        self.git('update-index', '--add', '--cacheinfo', f'160000,{oid},module')
        with self.assertRaisesRegex(WorkspaceTransactionError, 'submódulos'):
            self.transaction().prepare()

    def test_symlink_in_sandbox_cannot_overwrite_external_file(self):
        self.write('a.txt', 'baseline')
        self.commit()
        transaction = self.transaction()
        sandbox = Path(transaction.prepare())
        external = self.root / 'external.txt'
        external.write_text('external safe')
        try:
            (sandbox / 'link.txt').symlink_to(external)
        except OSError:
            self.skipTest('This Windows account cannot create symbolic links')
        with self.assertRaisesRegex(WorkspaceTransactionError, 'enlaces'):
            transaction.publish()
        self.assertEqual(external.read_text(), 'external safe')
        self.assertFalse((self.source / 'link.txt').exists())

    def test_windows_junction_in_sandbox_is_rejected(self):
        if os.name != 'nt':
            self.skipTest('Windows junction test')
        self.write('a.txt', 'baseline')
        self.commit()
        transaction = self.transaction()
        sandbox = Path(transaction.prepare())
        external = self.root / 'external'
        external.mkdir()
        (external / 'safe.txt').write_text('external safe')
        junction = sandbox / 'junction'
        result = subprocess.run(['cmd', '/c', 'mklink', '/J', str(junction), str(external)],
                                capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode:
            self.skipTest('This Windows account cannot create a junction')
        try:
            with self.assertRaisesRegex(WorkspaceTransactionError, 'junctions'):
                transaction.publish()
            self.assertEqual((external / 'safe.txt').read_text(), 'external safe')
        finally:
            junction.rmdir()

    def test_path_traversal_and_git_metadata_paths_are_rejected(self):
        for name in ('../outside', '/absolute', 'C:/outside', '.git/config', 'folder/../outside'):
            with self.subTest(name=name), self.assertRaises(WorkspaceTransactionError):
                WorkspaceTransaction._path(self.source, name)

    def test_write_failure_rolls_back_previous_replacements_and_retains_recovery(self):
        self.write('a.txt', 'a baseline')
        self.write('b.txt', 'b baseline')
        self.commit()
        transaction = self.transaction()
        sandbox = Path(transaction.prepare())
        (sandbox / 'a.txt').write_text('mission a')
        (sandbox / 'b.txt').write_text('mission b')
        real_replace = os.replace
        calls = []

        def fail_second(source, target):
            calls.append(target)
            if len(calls) == 2:
                raise PermissionError('fixture write failure')
            return real_replace(source, target)

        with patch('app.workspace_transaction.os.replace', side_effect=fail_second), self.assertRaises(WorkspaceTransactionError):
            transaction.publish()
        self.assertEqual((self.source / 'a.txt').read_text(), 'a baseline')
        self.assertEqual((self.source / 'b.txt').read_text(), 'b baseline')
        self.assertTrue(Path(transaction.recovery_path).exists())
        self.assertFalse(list(self.source.glob('.slimeops-*.tmp')))

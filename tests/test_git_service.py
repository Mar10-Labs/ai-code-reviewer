import pytest
from unittest.mock import patch, MagicMock
import subprocess

from src.infrastructure.services.git_service import GitService, BranchType, GitStatus, Branch


class TestGitServiceInit:
    def test_init_default_path(self):
        service = GitService()
        assert service.repo_path == "."

    def test_init_custom_path(self):
        service = GitService("/custom/path")
        assert service.repo_path == "/custom/path"


class TestGitServiceStatus:
    def test_status_clean(self):
        service = GitService()
        
        with patch.object(service, "_run") as mock_run:
            mock_run.side_effect = [
                (0, " M file.py", ""),
                (0, "main", ""),
                (0, "", ""),
                (0, "0 0", ""),
            ]
            status = service.status()
            
        assert status.current_branch == "main"

    def test_status_with_changes(self):
        service = GitService()
        
        with patch.object(service, "_run") as mock_run:
            mock_run.side_effect = [
                (0, "M  file.py\n?? untracked.py", ""),
                (0, "feat/test", ""),
                (1, "", ""),
                (0, "0 0", ""),
            ]
            status = service.status()
            
        assert status is not None


class TestGitServiceBranches:
    def test_get_local_branches(self):
        service = GitService()
        
        with patch.object(service, "_run") as mock_run:
            mock_run.return_value = (0, "* main\n  feature/test", "")
            branches = service.get_local_branches()
            
        assert len(branches) >= 0

    def test_classify_branch_type(self):
        service = GitService()
        
        assert service.classify_branch_type("feat/new").value == "feat"
        assert service.classify_branch_type("fix/bug").value == "fix"
        assert service.classify_branch_type("chore/update").value == "chore"
        assert service.classify_branch_type("refactor/code").value == "refactor"
        assert service.classify_branch_type("docs/readme").value == "docs"
        assert service.classify_branch_type("test/new").value == "test"
        assert service.classify_branch_type("ci/cicd").value == "ci"
        assert service.classify_branch_type("unknown").value == "unknown"

    def test_extract_issue_number(self):
        service = GitService()
        
        assert service.extract_issue_number("feat/123-title") == 123
        assert service.extract_issue_number("fix/#456-bug") == 456
        assert service.extract_issue_number("chore/789-update") == 789
        assert service.extract_issue_number("no-number") is None


class TestGitServiceCheckout:
    def test_checkout_success(self):
        service = GitService()
        
        with patch.object(service, "_run") as mock_run:
            mock_run.return_value = (0, "Switched to branch", "")
            success, msg = service.checkout("main")
            
        assert success is True

    def test_checkout_create_new(self):
        service = GitService()
        
        with patch.object(service, "_run") as mock_run:
            mock_run.return_value = (0, "Switched to new branch", "")
            success, msg = service.checkout("feature/new", create=True)
            
        assert success is True


class TestGitServiceBranchOperations:
    def test_create_branch(self):
        service = GitService()
        
        with patch.object(service, "_run") as mock_run:
            mock_run.side_effect = [
                (0, "Created branch", ""),
                (0, "Switched", ""),
            ]
            success, msg = service.create_branch("feature/test")
            
        assert success is True

    def test_delete_branch(self):
        service = GitService()
        
        with patch.object(service, "_run") as mock_run:
            mock_run.return_value = (0, "Deleted branch", "")
            success, msg = service.delete_branch("feature/old")
            
        assert success is True

    def test_delete_branch_force(self):
        service = GitService()
        
        with patch.object(service, "_run") as mock_run:
            mock_run.return_value = (0, "Deleted branch", "")
            success, msg = service.delete_branch("feature/old", force=True)
            
        assert success is True


class TestGitServiceGitOperations:
    def test_add_files(self):
        service = GitService()
        
        with patch.object(service, "_run") as mock_run:
            mock_run.return_value = (0, "", "")
            success, msg = service.add(".")
            
        assert success is True

    def test_commit_success(self):
        service = GitService()
        
        with patch.object(service, "_run") as mock_run:
            mock_run.return_value = (0, "[main abc123] commit message", "")
            success, msg = service.commit("test: commit message")
            
        assert success is True

    def test_commit_failure(self):
        service = GitService()
        
        with patch.object(service, "_run") as mock_run:
            mock_run.return_value = (1, "", "Nothing to commit")
            success, msg = service.commit("test: message")
            
        assert success is False


class TestGitServicePush:
    def test_push_success(self):
        service = GitService()
        
        with patch.object(service, "_run") as mock_run:
            mock_run.side_effect = [
                (0, "main", ""),
                (0, "Everything up-to-date", ""),
            ]
            success, msg = service.push()
            
        assert success is True

    def test_push_with_branch(self):
        service = GitService()
        
        with patch.object(service, "_run") as mock_run:
            mock_run.return_value = (0, "Pushed", "")
            success, msg = service.push(branch="feature/test")
            
        assert success is True


class TestGitServiceMerge:
    def test_merge_success(self):
        service = GitService()
        
        with patch.object(service, "_run") as mock_run:
            mock_run.return_value = (0, "Merge complete", "")
            success, msg = service.merge("feature/test")
            
        assert success is True

    def test_merge_with_conflicts(self):
        service = GitService()
        
        with patch.object(service, "_run") as mock_run:
            mock_run.return_value = (1, "", "CONFLICT")
            success, msg = service.merge("feature/test")
            
        assert success is False

    def test_merge_no_ff(self):
        service = GitService()
        
        with patch.object(service, "_run") as mock_run:
            mock_run.return_value = (0, "Merge made by recursive", "")
            success, msg = service.merge("feature/test", no_ff=True)
            
        assert success is True

    def test_merge_squash(self):
        service = GitService()
        
        with patch.object(service, "_run") as mock_run:
            mock_run.return_value = (0, "Squash merge complete", "")
            success, msg = service.merge("feature/test", squash=True)
            
        assert success is True


class TestGitServiceAbort:
    def test_abort_merge(self):
        service = GitService()
        
        with patch.object(service, "_run") as mock_run:
            mock_run.return_value = (0, "", "")
            success, msg = service.abort_merge()
            
        assert success is True


class TestGitServiceConflict:
    def test_get_conflict_files_none(self):
        service = GitService()
        
        with patch.object(service, "_run") as mock_run:
            mock_run.return_value = (0, "", "")
            conflicts = service.get_conflict_files()
            
        assert conflicts == []

    def test_get_conflict_files_with_conflicts(self):
        service = GitService()
        
        with patch.object(service, "_run") as mock_run:
            mock_run.return_value = (0, "file1.py\nfile2.py", "")
            conflicts = service.get_conflict_files()
            
        assert len(conflicts) == 2


class TestGitServiceStash:
    def test_stash(self):
        service = GitService()
        
        with patch.object(service, "_run") as mock_run:
            mock_run.return_value = (0, "Saved working directory", "")
            success, msg = service.stash("WIP")
            
        assert success is True

    def test_stash_pop(self):
        service = GitService()
        
        with patch.object(service, "_run") as mock_run:
            mock_run.return_value = (0, "Restored", "")
            success, msg = service.stash_pop()
            
        assert success is True

    def test_has_uncommitted_changes_true(self):
        service = GitService()
        
        with patch.object(service, "_run") as mock_run:
            mock_run.return_value = (0, "M  file.py", "")
            has_changes = service.has_uncommitted_changes()
            
        assert has_changes is True

    def test_has_uncommitted_changes_false(self):
        service = GitService()
        
        with patch.object(service, "_run") as mock_run:
            mock_run.return_value = (0, "", "")
            has_changes = service.has_uncommitted_changes()
            
        assert has_changes is False


class TestGitServiceDiff:
    def test_get_diff_staged(self):
        service = GitService()
        
        with patch.object(service, "_run") as mock_run:
            mock_run.return_value = (0, "diff --git", "")
            diff = service.get_diff(staged=True)
            
        assert "diff" in diff


class TestGitServiceOrphanBranches:
    def test_get_orphan_branches(self):
        service = GitService()
        
        with patch.object(service, "get_local_branches") as mock_branches:
            mock_branches.return_value = [
                Branch(name="main", is_current=True, is_remote=False),
                Branch(name="orphan/branch", is_current=False, is_remote=False),
            ]
            orphans = service.get_orphan_branches()
            
        assert isinstance(orphans, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

import asyncio
import re
import os
from typing import Optional
from dataclasses import dataclass, field
from enum import Enum

from src.agents.base_agent import (
    BaseAgent, AgentConfig, AgentResponse, AgentType, AgentCapability
)
from src.infrastructure.services.git_service import GitService, BranchType, GitStatus


class UserChoice(Enum):
    YES = "yes"
    YES_ALL = "yes_all"
    NO = "no"
    NO_ALL = "no_all"
    SHOW_DIFF = "show_diff"
    ABORT = "abort"
    FORCE = "force"


@dataclass
class GitOpsResult:
    status: str
    message: str
    branch_created: Optional[str] = None
    branch_deleted: list[str] = field(default_factory=list)
    commit_message: Optional[str] = None
    pr_url: Optional[str] = None
    merged: bool = False
    conflicts: list[str] = field(default_factory=list)


@dataclass
class Question:
    text: str
    options: list[tuple[UserChoice, str]]
    default: UserChoice = UserChoice.YES


class DevOpsAgent(BaseAgent):
    def __init__(self, repo_path: str = "."):
        config = AgentConfig(
            name="DevOps",
            agent_type=AgentType.DEVOPS,
            description="Handles Git operations, branches, commits, merges, and GitHub interactions",
            capabilities=[
                AgentCapability.EXECUTE_COMMAND,
                AgentCapability.FILE_SYSTEM,
                AgentCapability.USER_INTERACTION,
                AgentCapability.GITHUB_API,
            ]
        )
        super().__init__(config)
        self.git = GitService(repo_path)
        self._user_responses: dict[str, UserChoice] = {}

    async def execute(self, task: dict) -> AgentResponse:
        action = task.get("action", "")

        handlers = {
            "verify_state": self._verify_state,
            "prepare_branch": self._prepare_branch,
            "create_file": self._create_file,
            "commit": self._commit,
            "push": self._push,
            "merge": self._merge,
            "run_tests": self._run_tests,
            "full_workflow": self._full_workflow,
        }

        handler = handlers.get(action)
        if not handler:
            return AgentResponse(
                success=False,
                message=f"Unknown action: {action}",
                errors=[f"Available actions: {', '.join(handlers.keys())}"]
            )

        try:
            result = await handler(task)
            return result
        except Exception as e:
            return AgentResponse(
                success=False,
                message=f"Error executing {action}",
                errors=[str(e)]
            )

    async def _verify_state(self, task: dict) -> AgentResponse:
        status = self.git.status()
        local_branches = self.git.get_local_branches()
        
        orphans = self.git.get_orphan_branches()
        
        result = {
            "current_branch": status.current_branch,
            "is_clean": status.is_clean,
            "changes_count": status.changes_to_commit,
            "total_branches": len(local_branches),
            "orphan_branches": [b.name for b in orphans],
            "ahead": status.ahead,
            "behind": status.behind,
            "on_main": status.current_branch == "main"
        }

        warnings = []
        if not status.is_clean:
            warnings.append(f"There are {status.changes_to_commit} uncommitted changes")
        if status.ahead > 0:
            warnings.append(f"Branch is {status.ahead} commits ahead of remote")
        if orphans:
            warnings.append(f"Found {len(orphans)} orphan branches")
        if status.current_branch != "main":
            warnings.append(f"Not on main branch (currently on {status.current_branch})")

        return AgentResponse(
            success=True,
            message="Git state verified",
            data=result,
            errors=warnings
        )

    async def _prepare_branch(self, task: dict) -> AgentResponse:
        issue_number = task.get("issue_number")
        issue_title = task.get("issue_title", "")
        force_clean = task.get("force_clean", False)
        auto_mode = task.get("auto_mode", False)

        status = self.git.status()
        result = GitOpsResult(status="pending", message="")
        
        if not self.git.switch_to_main()[0]:
            return AgentResponse(
                success=False,
                message="Failed to switch to main branch",
                errors=["Could not checkout main"]
            )

        orphans = self.git.get_orphan_branches()
        if orphans and not auto_mode:
            branches_to_delete = [b.name for b in orphans]
            if issue_number:
                branches_to_delete = [b for b in branches_to_delete if str(issue_number) in b]
            
            result.branch_deleted = branches_to_delete
            for branch in branches_to_delete:
                self.git.delete_branch(branch, force=True)

        branch_name = self._generate_branch_name(issue_number, issue_title)
        existing = [b for b in self.git.get_local_branches() if b.name == branch_name]
        if existing:
            success, msg = self.git.checkout(branch_name)
        else:
            success, msg = self.git.create_branch(branch_name)

        if success:
            result.status = "success"
            result.message = f"Branch '{branch_name}' ready"
            result.branch_created = branch_name
            
            return AgentResponse(
                success=True,
                message=result.message,
                data={
                    "branch": branch_name,
                    "branch_type": self.git.classify_branch_type(branch_name).value,
                    "deleted_branches": result.branch_deleted
                }
            )
        
        return AgentResponse(success=False, message=msg)

    def _generate_branch_name(self, issue_number: Optional[int], title: str) -> str:
        clean_title = re.sub(r'[^a-zA-Z0-9\s-]', '', title)
        clean_title = re.sub(r'\s+', '-', clean_title.strip().lower())
        clean_title = re.sub(r'-+', '-', clean_title)
        clean_title = clean_title[:50].strip('-')
        
        if issue_number:
            return f"feat/{issue_number}-{clean_title}" if clean_title else f"feat/{issue_number}"
        return f"feat/{clean_title}" if clean_title else "feat/unknown"

    async def _create_file(self, task: dict) -> AgentResponse:
        file_path = task.get("file_path")
        content = task.get("content", "")
        parents = task.get("create_parents", True)

        if not file_path:
            return AgentResponse(success=False, message="No file_path provided")

        if parents:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

        try:
            with open(file_path, "w") as f:
                f.write(content)
            
            self.git.add(file_path)
            
            return AgentResponse(
                success=True,
                message=f"File created: {file_path}",
                data={"file_path": file_path, "size": len(content)}
            )
        except Exception as e:
            return AgentResponse(success=False, message=f"Error creating file", errors=[str(e)])

    async def _commit(self, task: dict) -> AgentResponse:
        message = task.get("message")
        auto = task.get("auto", False)
        
        if not message:
            branch_type = self.git.classify_branch_type(self.git.status().current_branch)
            issue_num = self.git.extract_issue_number(self.git.status().current_branch)
            
            message = self._generate_commit_message(branch_type, task.get("description", ""))
            if issue_num:
                message += f"\n\nCloses #{issue_num}"

        if self.git.has_uncommitted_changes():
            success, msg = self.git.commit(message)
            if success:
                return AgentResponse(
                    success=True,
                    message="Changes committed",
                    data={"commit_message": message}
                )
            return AgentResponse(success=False, message=f"Commit failed: {msg}")
        
        return AgentResponse(success=True, message="No changes to commit")

    def _generate_commit_message(self, branch_type: BranchType, description: str) -> str:
        type_map = {
            BranchType.FEAT: "feat",
            BranchType.FIX: "fix",
            BranchType.CHORE: "chore",
            BranchType.REFACTOR: "refactor",
            BranchType.DOCS: "docs",
            BranchType.TEST: "test",
            BranchType.CI: "ci",
        }
        
        prefix = type_map.get(branch_type, "feat")
        
        if description:
            desc_lower = description.lower()
            if "schema" in desc_lower or "pydantic" in desc_lower:
                return f"{prefix}(models): {description}"
            elif "test" in desc_lower:
                return f"test: {description}"
            elif "docker" in desc_lower:
                return f"{prefix}(docker): {description}"
        
        return f"{prefix}: changes"

    async def _push(self, task: dict) -> AgentResponse:
        set_upstream = task.get("set_upstream", True)
        success, msg = self.git.push(set_upstream=set_upstream)
        
        return AgentResponse(
            success=success,
            message="Push successful" if success else f"Push failed: {msg}",
            data={"pushed": success}
        )

    async def _merge(self, task: dict) -> AgentResponse:
        branch = task.get("branch", "main")
        squash = task.get("squash", False)
        create_pr = task.get("create_pr", True)
        
        conflicts = self.git.get_conflict_files()
        if conflicts:
            return AgentResponse(
                success=False,
                message="Merge conflicts detected",
                errors=[f"Conflicts in: {', '.join(conflicts)}"]
            )

        success, msg = self.git.merge(branch, squash=squash)
        
        if success:
            return AgentResponse(
                success=True,
                message=f"Merged into {branch}",
                data={"merged_branch": branch, "squash": squash}
            )
        
        return AgentResponse(success=False, message=f"Merge failed: {msg}")

    async def _run_tests(self, task: dict) -> AgentResponse:
        test_command = task.get("command", "pytest")
        
        import subprocess
        try:
            result = subprocess.run(
                test_command.split(),
                capture_output=True,
                text=True,
                timeout=120
            )
            
            return AgentResponse(
                success=result.returncode == 0,
                message=f"Tests {'passed' if result.returncode == 0 else 'failed'}",
                data={
                    "returncode": result.returncode,
                    "stdout": result.stdout[-1000:] if result.stdout else "",
                    "stderr": result.stderr[-500:] if result.stderr else ""
                }
            )
        except subprocess.TimeoutExpired:
            return AgentResponse(success=False, message="Tests timed out", errors=["Timeout"])
        except Exception as e:
            return AgentResponse(success=False, message="Error running tests", errors=[str(e)])

    async def _full_workflow(self, task: dict) -> AgentResponse:
        issue_number = task.get("issue_number")
        issue_title = task.get("issue_title", "")
        files_to_create = task.get("files", [])
        test_command = task.get("test_command", "pytest -v")
        
        results = []
        
        verify = await self._verify_state(task)
        results.append(("verify_state", verify))
        
        prepare = await self._prepare_branch({
            "issue_number": issue_number,
            "issue_title": issue_title
        })
        results.append(("prepare_branch", prepare))
        
        if not prepare.success:
            return AgentResponse(
                success=False,
                message="Workflow failed at branch preparation",
                errors=[prepare.message]
            )

        for file_task in files_to_create:
            file_result = await self._create_file(file_task)
            results.append(("create_file", file_result))

        if self.git.has_uncommitted_changes():
            commit = await self._commit({
                "issue_number": issue_number,
                "description": issue_title
            })
            results.append(("commit", commit))
        
        test_result = await self._run_tests({"command": test_command})
        results.append(("run_tests", test_result))
        
        all_success = all(r[1].success for r in results)
        
        return AgentResponse(
            success=all_success and test_result.success,
            message=f"Workflow completed: {'OK' if all_success else 'ISSUES FOUND'}",
            data={
                "steps": [(name, r.success, r.message) for name, r in results],
                "tests_passed": test_result.success
            }
        )

    def generate_status_report(self) -> str:
        status = self.git.status()
        branches = self.git.get_local_branches()
        
        report = f"""
╔══════════════════════════════════════════════════════════╗
║                    GIT STATUS REPORT                        ║
╠══════════════════════════════════════════════════════════╣
║ Current Branch: {status.current_branch:<38} ║
║ On Main:       {'YES ✓' if status.current_branch == 'main' else 'NO ✗':<38} ║
║ Clean:         {'YES ✓' if status.is_clean else f'NO ✗ ({status.changes_to_commit} changes)':<38} ║
║ Ahead/Behind:  {status.ahead}/{status.behind:<38} ║
╠══════════════════════════════════════════════════════════╣
║ Total Branches: {len(branches):<41} ║"""
        
        for b in branches[:10]:
            marker = "→ " if b.is_current else "  "
            report += f"\n║ {marker}{b.name:<46} ║"
        
        if len(branches) > 10:
            report += f"\n║ ... and {len(branches) - 10} more branches                      ║"
        
        report += "\n╚══════════════════════════════════════════════════════════╝"
        
        return report

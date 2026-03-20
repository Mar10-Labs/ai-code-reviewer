import subprocess
import re
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class BranchType(Enum):
    FEAT = "feat"
    FIX = "fix"
    CHORE = "chore"
    REFACTOR = "refactor"
    DOCS = "docs"
    TEST = "test"
    CI = "ci"
    UNKNOWN = "unknown"


@dataclass
class GitStatus:
    current_branch: str
    is_clean: bool
    changes_to_commit: int = 0
    untracked_files: int = 0
    staged_files: int = 0
    ahead: int = 0
    behind: int = 0


@dataclass
class Branch:
    name: str
    is_current: bool
    is_remote: bool = False
    last_commit: str = ""
    last_commit_message: str = ""


@dataclass
class Issue:
    number: int
    title: str
    state: str
    labels: list[str] = field(default_factory=list)


class GitService:
    def __init__(self, repo_path: str = "."):
        self.repo_path = repo_path

    def _run(self, *args, capture: bool = True) -> tuple[int, str, str]:
        try:
            result = subprocess.run(
                ["git"] + list(args),
                cwd=self.repo_path,
                capture_output=capture,
                text=True
            )
            return result.returncode, result.stdout.strip(), result.stderr.strip()
        except FileNotFoundError:
            return 1, "", "git not found"

    def status(self) -> GitStatus:
        _, stdout, _ = self._run("status", "--porcelain")
        
        code, current, _ = self._run("branch", "--show-current")
        current_branch = current if code == 0 else "unknown"
        
        _, clean_status, _ = self._run("diff", "--quiet")
        is_clean = clean_status == ""
        
        changes = 0
        untracked = 0
        staged = 0
        for line in stdout.split("\n"):
            if not line:
                continue
            if line.startswith("??"):
                untracked += 1
            elif line[0] in ["M", "A", "D"]:
                staged += 1
                changes += 1
            elif line[1] in ["M", "D"]:
                changes += 1
        
        _, ahead_out, _ = self._run("rev-list", "--left-right", "--count", 
                                     f"{current_branch}...origin/{current_branch}")
        ahead, behind = 0, 0
        if ahead_out:
            parts = ahead_out.split()
            if len(parts) == 2:
                behind, ahead = int(parts[0]), int(parts[1])
        
        return GitStatus(
            current_branch=current_branch,
            is_clean=is_clean,
            changes_to_commit=changes,
            untracked_files=untracked,
            staged_files=staged,
            ahead=ahead,
            behind=behind
        )

    def get_branches(self, local: bool = True, remote: bool = False) -> list[Branch]:
        branches = []
        flag = ""
        if local and not remote:
            flag = "--list"
        elif remote and not local:
            flag = "--list", "-r"
        
        args = ["branch"] + (list(flag) if flag else ["--list"])
        _, stdout, _ = self._run(*args)
        
        for line in stdout.split("\n"):
            if not line.strip():
                continue
            is_current = line.startswith("*")
            name = line.lstrip("* ").strip()
            is_remote = "/" in name and not name.startswith("HEAD")
            
            _, commit, _ = self._run("log", "-1", "--format=%H", name) if name else (1, "", "")
            _, msg, _ = self._run("log", "-1", "--format=%s", name) if name else (1, "", "")
            
            branches.append(Branch(
                name=name,
                is_current=is_current,
                is_remote=is_remote,
                last_commit=commit,
                last_commit_message=msg
            ))
        
        return branches

    def get_local_branches(self) -> list[Branch]:
        return [b for b in self.get_branches() if not b.is_remote]

    def get_orphan_branches(self, base_branch: str = "main") -> list[Branch]:
        all_branches = self.get_local_branches()
        orphans = []
        
        for branch in all_branches:
            if branch.is_current or branch.name == base_branch:
                continue
            
            code, _, _ = self._run("log", f"{base_branch}..{branch.name}", "--oneline")
            if code != 0:
                orphans.append(branch)
        
        return orphans

    def checkout(self, branch: str, create: bool = False) -> tuple[bool, str]:
        args = ["checkout"]
        if create:
            args.append("-b")
        args.append(branch)
        
        code, stdout, stderr = self._run(*args)
        return code == 0, stdout or stderr

    def switch_to_main(self) -> tuple[bool, str]:
        return self.checkout("main")

    def create_branch(self, name: str, switch: bool = True) -> tuple[bool, str]:
        code, out, err = self._run("branch", name)
        if code != 0:
            return False, err
        
        if switch:
            success, msg = self.checkout(name)
            return success, msg
        
        return True, f"Branch '{name}' created"

    def delete_branch(self, name: str, force: bool = False) -> tuple[bool, str]:
        flag = "-D" if force else "-d"
        code, out, err = self._run("branch", flag, name)
        return code == 0, out or err

    def add(self, files: str = ".") -> tuple[bool, str]:
        code, _, err = self._run("add", files)
        return code == 0, err if code != 0 else "Files staged"

    def commit(self, message: str) -> tuple[bool, str]:
        code, out, err = self._run("commit", "-m", message)
        if code != 0:
            return False, err
        return True, out

    def push(self, remote: str = "origin", branch: Optional[str] = None, set_upstream: bool = True) -> tuple[bool, str]:
        if branch is None:
            _, branch_result, _ = self._run("branch", "--show-current")
            if not branch_result:
                return False, "No branch found"
            branch = branch_result
        
        args = ["push"]
        if set_upstream:
            args.extend(["-u", remote, branch])
        else:
            args.extend([remote, branch])
        
        code, out, err = self._run(*args)
        return code == 0, out or err

    def get_stash_list(self) -> list[str]:
        _, stdout, _ = self._run("stash", "list", "--format=%gd")
        return stdout.split("\n") if stdout else []

    def stash(self, message: str = "") -> tuple[bool, str]:
        args = ["stash", "push"]
        if message:
            args.extend(["-m", message])
        code, out, err = self._run(*args)
        return code == 0, out or err

    def stash_pop(self) -> tuple[bool, str]:
        code, out, err = self._run("stash", "pop")
        return code == 0, out or err

    def has_uncommitted_changes(self) -> bool:
        _, stdout, _ = self._run("status", "--porcelain")
        return bool(stdout.strip())

    def get_diff(self, staged: bool = False) -> str:
        _, stdout, _ = self._run("diff", "--cached" if staged else "")
        return stdout

    def classify_branch_type(self, branch_name: str) -> BranchType:
        prefix = branch_name.split("/")[0] if "/" in branch_name else branch_name.split("-")[0]
        
        mapping = {
            "feat": BranchType.FEAT,
            "feature": BranchType.FEAT,
            "fix": BranchType.FIX,
            "bugfix": BranchType.FIX,
            "hotfix": BranchType.FIX,
            "chore": BranchType.CHORE,
            "refactor": BranchType.REFACTOR,
            "docs": BranchType.DOCS,
            "test": BranchType.TEST,
            "ci": BranchType.CI,
        }
        
        return mapping.get(prefix.lower(), BranchType.UNKNOWN)

    def extract_issue_number(self, branch_name: str) -> Optional[int]:
        match = re.search(r'#?(\d+)', branch_name)
        if match:
            return int(match.group(1))
        return None

    def merge(self, branch: str, no_ff: bool = False, squash: bool = False) -> tuple[bool, str]:
        args = ["merge"]
        if no_ff:
            args.append("--no-ff")
        if squash:
            args.append("--squash")
        args.append(branch)
        
        code, out, err = self._run(*args)
        
        if "CONFLICT" in (out + err):
            return False, f"Merge conflict in {err}"
        
        return code == 0, out or err

    def abort_merge(self) -> tuple[bool, str]:
        code, _, err = self._run("merge", "--abort")
        return code == 0, err if code != 0 else "Merge aborted"

    def get_conflict_files(self) -> list[str]:
        _, stdout, _ = self._run("diff", "--name-only", "--diff-filter=U")
        return stdout.split("\n") if stdout else []

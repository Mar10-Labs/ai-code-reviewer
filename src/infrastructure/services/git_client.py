import subprocess
from typing import Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class BlameLine:
    commit_hash: str
    author: str
    date: datetime
    line_content: str
    line_number: int


@dataclass
class FileBlame:
    file_path: str
    lines: list[BlameLine]
    total_lines: int
    authors: dict[str, int]
    last_modified: datetime


@dataclass
class GitHistory:
    commit_hash: str
    author: str
    date: datetime
    message: str
    lines_added: int
    lines_deleted: int


class GitClient:
    def __init__(self, repo_path: str = "."):
        self.repo_path = repo_path

    def get_file_content(self, file_path: str, ref: Optional[str] = None) -> str:
        import subprocess
        cmd = ["git", "show", f"{ref}:{file_path}" if ref else f"HEAD:{file_path}"]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.repo_path)
            return result.stdout if result.returncode == 0 else ""
        except Exception:
            return ""

    def get_file_blame(self, file_path: str) -> FileBlame:
        import subprocess
        from datetime import datetime
        
        blame_lines = []
        authors: dict[str, int] = {}
        last_modified = datetime.now()
        
        try:
            result = subprocess.run(
                ["git", "blame", "--line-porcelain", file_path],
                capture_output=True,
                text=True,
                cwd=self.repo_path
            )
            
            if result.returncode != 0:
                return FileBlame(file_path, [], 0, {}, datetime.now())
            
            lines = result.stdout.split("\n")
            current_commit = ""
            current_author = ""
            current_date = datetime.now()
            current_line_num = 0
            current_content = ""
            
            for line in lines:
                if line.startswith("commit "):
                    current_commit = line[7:]
                elif line.startswith("author "):
                    current_author = line[8:]
                    authors[current_author] = authors.get(current_author, 0) + 1
                elif line.startswith("author-time "):
                    timestamp = int(line.split()[1])
                    current_date = datetime.fromtimestamp(timestamp)
                    if current_date > last_modified:
                        last_modified = current_date
                elif line.startswith("\t"):
                    current_content = line[1:]
                    current_line_num += 1
                    blame_lines.append(BlameLine(
                        commit_hash=current_commit,
                        author=current_author,
                        date=current_date,
                        line_content=current_content,
                        line_number=current_line_num
                    ))
                elif line.startswith("filename "):
                    pass
                    
        except Exception:
            pass
        
        return FileBlame(
            file_path=file_path,
            lines=blame_lines,
            total_lines=len(blame_lines),
            authors=authors,
            last_modified=last_modified
        )

    def get_file_history(self, file_path: str, limit: int = 10) -> list[GitHistory]:
        import subprocess
        from datetime import datetime
        
        history = []
        
        try:
            result = subprocess.run(
                ["git", "log", f"--oneline", "-{limit}", "--", file_path],
                capture_output=True,
                text=True,
                cwd=self.repo_path
            )
            
            if result.returncode != 0:
                return []
            
            for line in result.stdout.strip().split("\n"):
                if not line.strip():
                    continue
                
                parts = line.split(" ", 1)
                if len(parts) == 2:
                    commit_hash = parts[0]
                    message = parts[1]
                    
                    date_result = subprocess.run(
                        ["git", "log", "-1", "--format=%ai", commit_hash, "--", file_path],
                        capture_output=True,
                        text=True,
                        cwd=self.repo_path
                    )
                    
                    if date_result.returncode == 0:
                        date_str = date_result.stdout.strip()
                        try:
                            date = datetime.fromisoformat(date_str.replace(" ", "T").split("+")[0])
                        except:
                            date = datetime.now()
                    else:
                        date = datetime.now()
                        
                        history.append(GitHistory(
                            commit_hash=commit_hash,
                            author="",
                            date=date,
                            message=message,
                            lines_added=0,
                            lines_deleted=0
                        ))
                        
        except Exception:
            pass
        
        return history

    def is_file_hot(self, file_path: str, days: int = 30) -> bool:
        from datetime import datetime, timedelta
        
        try:
            result = subprocess.run(
                ["git", "log", f"--since={days}.days", "--oneline", "--", file_path],
                capture_output=True,
                text=True,
                cwd=self.repo_path
            )
            
            if result.returncode == 0:
                commits = len([l for l in result.stdout.strip().split("\n") if l.strip()])
                return commits > 5
        except Exception:
            pass
        
        return False

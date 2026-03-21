from dataclasses import dataclass
from typing import Optional
from enum import Enum
import hmac
import hashlib
import time


class WebhookEventType(str, Enum):
    PULL_REQUEST = "pull_request"
    PUSH = "push"
    ISSUE_COMMENT = "issue_comment"
    CHECK_RUN = "check_run"
    CHECK_SUITE = "check_suite"


class WebhookValidationError(Exception):
    pass


class WebhookHMACError(WebhookValidationError):
    pass


class WebhookPayloadError(WebhookValidationError):
    pass


class WebhookDeduplicationError(WebhookValidationError):
    pass


@dataclass
class GitHubWebhookPayload:
    event_type: str
    action: Optional[str]
    delivery_id: str
    repository: str
    pr_number: Optional[int]
    pr_title: Optional[str]
    pr_author: Optional[str]
    sender: str
    before: Optional[str]
    after: Optional[str]
    ref: Optional[str]
    files_changed: list[str]
    raw_payload: dict


class WebhookValidator:
    def __init__(self, secret: str = None, secret_env_var: str = "GITHUB_WEBHOOK_SECRET"):
        self.secret = secret or self._get_secret_from_env(secret_env_var)
        self.tolerance_seconds = 300

    def _get_secret_from_env(self, env_var: str) -> str:
        import os
        return os.getenv(env_var, "")

    def validate_hmac(self, payload: bytes, signature: str, timestamp: str = None) -> bool:
        if not self.secret:
            return True

        if signature.startswith("sha256="):
            expected = signature[7:]
        elif signature.startswith("sha1="):
            expected = signature[5:]
        else:
            expected = signature

        if timestamp:
            try:
                ts = int(timestamp)
                current_time = int(time.time())
                if abs(current_time - ts) > self.tolerance_seconds:
                    return False
            except ValueError:
                return False

        if timestamp:
            payload_to_sign = f"{timestamp}.".encode() + payload
        else:
            payload_to_sign = payload

        mac = hmac.new(
            self.secret.encode(),
            payload_to_sign,
            hashlib.sha256
        )
        computed = mac.hexdigest()

        return hmac.compare_digest(computed, expected)

    def verify_signature(self, payload: bytes, signature: str) -> bool:
        if not self.secret:
            return True

        expected = hmac.new(
            self.secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(f"sha256={expected}", signature)


class WebhookParser:
    @staticmethod
    def parse_pull_request(payload: dict, delivery_id: str) -> GitHubWebhookPayload:
        pr = payload.get("pull_request", {})
        repo = payload.get("repository", {})
        
        files_changed = []
        if "changed_files" in pr:
            files_changed = [f.get("filename", "") for f in payload.get("files", [])]

        return GitHubWebhookPayload(
            event_type=WebhookEventType.PULL_REQUEST,
            action=payload.get("action"),
            delivery_id=delivery_id,
            repository=repo.get("full_name", ""),
            pr_number=pr.get("number"),
            pr_title=pr.get("title"),
            pr_author=pr.get("user", {}).get("login"),
            sender=payload.get("sender", {}).get("login", ""),
            before=pr.get("base", {}).get("sha"),
            after=pr.get("head", {}).get("sha"),
            ref=pr.get("head", {}).get("ref"),
            files_changed=files_changed,
            raw_payload=payload
        )

    @staticmethod
    def parse_push(payload: dict, delivery_id: str) -> GitHubWebhookPayload:
        repo = payload.get("repository", {})
        
        commits = payload.get("commits", [])
        files_changed = []
        for commit in commits:
            for file in commit.get("added", []) + commit.get("modified", []):
                if file not in files_changed:
                    files_changed.append(file)

        return GitHubWebhookPayload(
            event_type=WebhookEventType.PUSH,
            action="push",
            delivery_id=delivery_id,
            repository=repo.get("full_name", ""),
            pr_number=None,
            pr_title=None,
            pr_author=payload.get("pusher", {}).get("name"),
            sender=payload.get("sender", {}).get("login", ""),
            before=payload.get("before"),
            after=payload.get("after"),
            ref=payload.get("ref"),
            files_changed=files_changed,
            raw_payload=payload
        )

    @staticmethod
    def parse(payload: dict, event: str, delivery_id: str) -> GitHubWebhookPayload:
        if event == "pull_request":
            return WebhookParser.parse_pull_request(payload, delivery_id)
        elif event == "push":
            return WebhookParser.parse_push(payload, delivery_id)
        else:
            return GitHubWebhookPayload(
                event_type=event,
                action=payload.get("action"),
                delivery_id=delivery_id,
                repository=payload.get("repository", {}).get("full_name", ""),
                pr_number=None,
                pr_title=None,
                pr_author=None,
                sender=payload.get("sender", {}).get("login", ""),
                before=None,
                after=None,
                ref=None,
                files_changed=[],
                raw_payload=payload
            )


def validate_webhook_signature(
    payload: bytes,
    signature: str,
    secret: str = None
) -> bool:
    validator = WebhookValidator(secret)
    return validator.verify_signature(payload, signature)


def parse_github_webhook(
    payload: dict,
    event: str,
    delivery_id: str
) -> GitHubWebhookPayload:
    return WebhookParser.parse(payload, event, delivery_id)

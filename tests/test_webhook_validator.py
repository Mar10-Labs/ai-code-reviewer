import pytest
import hmac
import hashlib
import time
from unittest.mock import patch

from src.infrastructure.services.webhook_validator import (
    WebhookValidator,
    WebhookParser,
    WebhookEventType,
    validate_webhook_signature,
    parse_github_webhook,
)


class TestWebhookValidator:
    def test_validate_without_secret(self):
        with patch.dict("os.environ", {"GITHUB_WEBHOOK_SECRET": ""}, clear=True):
            validator = WebhookValidator(secret="")
            assert validator.verify_signature(b"payload", "sha256=abc") is True

    def test_validate_with_correct_signature(self):
        secret = "test_secret"
        payload = b'{"action": "opened"}'
        
        expected = hmac.new(
            secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        signature = f"sha256={expected}"
        
        validator = WebhookValidator(secret=secret)
        assert validator.verify_signature(payload, signature) is True

    def test_validate_with_incorrect_signature(self):
        validator = WebhookValidator(secret="test_secret")
        assert validator.verify_signature(b"payload", "sha256=wrong") is False

    def test_hmac_with_timestamp(self):
        secret = "test_secret"
        payload = b'{"action": "opened"}'
        timestamp = str(int(time.time()))
        
        payload_with_ts = f"{timestamp}.".encode() + payload
        
        mac = hmac.new(secret.encode(), payload_with_ts, hashlib.sha256)
        signature = f"sha256={mac.hexdigest()}"
        
        validator = WebhookValidator(secret=secret)
        assert validator.validate_hmac(payload, signature, timestamp) is True


class TestWebhookParser:
    def test_parse_pull_request(self):
        payload = {
            "action": "opened",
            "pull_request": {
                "number": 123,
                "title": "Test PR",
                "user": {"login": "testuser"},
                "base": {"sha": "abc123"},
                "head": {"sha": "def456", "ref": "feature/test"}
            },
            "repository": {
                "full_name": "owner/repo"
            },
            "sender": {"login": "sender"}
        }
        
        result = WebhookParser.parse_pull_request(payload, "delivery-id-123")
        
        assert result.event_type == WebhookEventType.PULL_REQUEST
        assert result.action == "opened"
        assert result.pr_number == 123
        assert result.pr_title == "Test PR"
        assert result.pr_author == "testuser"
        assert result.repository == "owner/repo"
        assert result.delivery_id == "delivery-id-123"

    def test_parse_push(self):
        payload = {
            "ref": "refs/heads/main",
            "before": "abc123",
            "after": "def456",
            "pusher": {"name": "testuser"},
            "repository": {
                "full_name": "owner/repo"
            },
            "commits": [
                {
                    "added": ["file1.py"],
                    "modified": ["file2.py"]
                }
            ],
            "sender": {"login": "sender"}
        }
        
        result = WebhookParser.parse_push(payload, "delivery-id-456")
        
        assert result.event_type == WebhookEventType.PUSH
        assert result.ref == "refs/heads/main"
        assert result.before == "abc123"
        assert result.after == "def456"
        assert "file1.py" in result.files_changed
        assert "file2.py" in result.files_changed

    def test_parse_unknown_event(self):
        payload = {
            "repository": {"full_name": "owner/repo"},
            "sender": {"login": "user"}
        }
        
        result = WebhookParser.parse(payload, "unknown_event", "delivery-id")
        
        assert result.event_type == "unknown_event"
        assert result.repository == "owner/repo"


class TestValidateWebhookSignature:
    def test_validate_with_secret(self):
        secret = "webhook_secret"
        payload = b'{"test": "data"}'
        
        mac = hmac.new(secret.encode(), payload, hashlib.sha256)
        signature = f"sha256={mac.hexdigest()}"
        
        assert validate_webhook_signature(payload, signature, secret) is True

    def test_validate_without_secret(self):
        with patch.dict("os.environ", {"GITHUB_WEBHOOK_SECRET": ""}, clear=True):
            assert validate_webhook_signature(b"payload", "sha256=anything", None) is True


class TestParseGitHubWebhook:
    def test_parse_pr_opened(self):
        payload = {
            "action": "opened",
            "pull_request": {
                "number": 1,
                "title": "New Feature",
                "user": {"login": "developer"},
                "base": {"sha": "base123"},
                "head": {"sha": "head456", "ref": "feature"}
            },
            "repository": {"full_name": "org/project"},
            "sender": {"login": "developer"}
        }
        
        result = parse_github_webhook(payload, "pull_request", "evt-123")
        
        assert result.pr_number == 1
        assert result.pr_title == "New Feature"
        assert result.action == "opened"

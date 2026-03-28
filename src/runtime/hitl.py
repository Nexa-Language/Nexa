"""
Nexa Human-in-the-Loop (HITL) Module

Provides primitives for suspending execution and waiting for human approval/input.

Usage in generated code:
    status = wait_for_human(prompt="Please review this plan", channel="Slack")
    status = wait_for_human(prompt="Approve?", timeout=300)  # 5 minute timeout
    
Return value is an ApprovalStatus enum:
    - ApprovalStatus.APPROVED: Human approved
    - ApprovalStatus.REJECTED: Human rejected
    - ApprovalStatus.TIMEOUT: Timeout waiting for response
    - ApprovalStatus.CANCELLED: Operation was cancelled
"""

import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union
from pathlib import Path
from datetime import datetime


class ApprovalStatus(Enum):
    """Status of human approval request"""
    APPROVED = "approved"
    REJECTED = "rejected"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    PENDING = "pending"
    
    def __bool__(self) -> bool:
        """Allow using status as boolean - True if approved"""
        return self == ApprovalStatus.APPROVED
    
    def __str__(self) -> str:
        return self.value


@dataclass
class ApprovalRequest:
    """Represents a pending approval request"""
    id: str
    prompt: str
    channel: str
    timeout: Optional[int] = None
    context: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    status: ApprovalStatus = ApprovalStatus.PENDING
    response: Optional[str] = None
    responder: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "prompt": self.prompt,
            "channel": self.channel,
            "timeout": self.timeout,
            "context": self.context,
            "created_at": self.created_at.isoformat(),
            "status": self.status.value,
            "response": self.response,
            "responder": self.responder
        }


class HITLBackend:
    """Base class for HITL backends (notification channels)"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
    
    def send_request(self, request: ApprovalRequest) -> bool:
        """Send approval request to channel. Returns True if sent successfully."""
        raise NotImplementedError
    
    def wait_for_response(self, request: ApprovalRequest, timeout: int) -> ApprovalStatus:
        """Wait for human response. Returns approval status."""
        raise NotImplementedError
    
    def cancel_request(self, request: ApprovalRequest) -> bool:
        """Cancel a pending request."""
        raise NotImplementedError


class CLIBackend(HITLBackend):
    """CLI-based HITL backend for local development/testing"""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self._pending_responses: Dict[str, ApprovalStatus] = {}
    
    def send_request(self, request: ApprovalRequest) -> bool:
        """Print approval request to console"""
        print("\n" + "=" * 60)
        print("🔔 HUMAN APPROVAL REQUIRED")
        print("=" * 60)
        print(f"Request ID: {request.id}")
        print(f"Channel: {request.channel}")
        print(f"Timeout: {request.timeout}s" if request.timeout else "Timeout: None")
        print("-" * 60)
        print(request.prompt)
        print("-" * 60)
        
        if request.context:
            print("Context:")
            for key, value in request.context.items():
                print(f"  {key}: {value}")
            print("-" * 60)
        
        return True
    
    def wait_for_response(self, request: ApprovalRequest, timeout: int) -> ApprovalStatus:
        """Wait for user input via CLI"""
        print("\nOptions: [y] Approve  [n] Reject  [c] Cancel  [s] Skip (timeout)")
        
        if timeout:
            print(f"Waiting up to {timeout} seconds...")
        
        start_time = time.time()
        
        while True:
            # Check timeout
            if timeout and (time.time() - start_time) > timeout:
                print("\n⏰ Timeout reached!")
                return ApprovalStatus.TIMEOUT
            
            # Check if response already provided
            if request.id in self._pending_responses:
                return self._pending_responses.pop(request.id)
            
            # Try to read input (non-blocking approach)
            try:
                # Use select for non-blocking input on Unix
                import select
                if select.select([sys.stdin], [], [], 1.0)[0]:
                    response = sys.stdin.readline().strip().lower()
                    
                    if response in ('y', 'yes', 'approve', 'a'):
                        print("✅ Approved!")
                        return ApprovalStatus.APPROVED
                    elif response in ('n', 'no', 'reject', 'r'):
                        print("❌ Rejected!")
                        return ApprovalStatus.REJECTED
                    elif response in ('c', 'cancel'):
                        print("🚫 Cancelled!")
                        return ApprovalStatus.CANCELLED
                    elif response in ('s', 'skip'):
                        print("⏰ Skipping (simulating timeout)...")
                        return ApprovalStatus.TIMEOUT
                    else:
                        print(f"Unknown response: {response}. Use y/n/c/s")
            except Exception:
                # On Windows or if select fails, use simple timeout check
                time.sleep(1.0)
        
        return ApprovalStatus.TIMEOUT
    
    def cancel_request(self, request: ApprovalRequest) -> bool:
        """Cancel pending request"""
        self._pending_responses.pop(request.id, None)
        return True


class FileBackend(HITLBackend):
    """File-based HITL backend for async approval workflow"""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.pending_dir = Path(config.get("pending_dir", ".nexa_pending"))
        self.approved_dir = Path(config.get("approved_dir", ".nexa_approved"))
        self.rejected_dir = Path(config.get("rejected_dir", ".nexa_rejected"))
        
        # Ensure directories exist
        for dir_path in [self.pending_dir, self.approved_dir, self.rejected_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
    
    def send_request(self, request: ApprovalRequest) -> bool:
        """Write request to pending directory"""
        request_file = self.pending_dir / f"{request.id}.json"
        try:
            with open(request_file, 'w') as f:
                json.dump(request.to_dict(), f, indent=2)
            return True
        except Exception as e:
            print(f"Error writing request file: {e}")
            return False
    
    def wait_for_response(self, request: ApprovalRequest, timeout: int) -> ApprovalStatus:
        """Poll for response file"""
        start_time = time.time()
        
        while True:
            # Check timeout
            if timeout and (time.time() - start_time) > timeout:
                return ApprovalStatus.TIMEOUT
            
            # Check approved directory
            approved_file = self.approved_dir / f"{request.id}.json"
            if approved_file.exists():
                try:
                    with open(approved_file) as f:
                        data = json.load(f)
                    request.response = data.get("response")
                    request.responder = data.get("responder")
                    approved_file.unlink()  # Clean up
                    return ApprovalStatus.APPROVED
                except Exception:
                    pass
            
            # Check rejected directory
            rejected_file = self.rejected_dir / f"{request.id}.json"
            if rejected_file.exists():
                try:
                    with open(rejected_file) as f:
                        data = json.load(f)
                    request.response = data.get("response")
                    request.responder = data.get("responder")
                    rejected_file.unlink()  # Clean up
                    return ApprovalStatus.REJECTED
                except Exception:
                    pass
            
            # Sleep before next check
            time.sleep(2.0)
        
        return ApprovalStatus.TIMEOUT
    
    def cancel_request(self, request: ApprovalRequest) -> bool:
        """Remove pending request file"""
        request_file = self.pending_dir / f"{request.id}.json"
        if request_file.exists():
            request_file.unlink()
        return True


class SlackBackend(HITLBackend):
    """Slack-based HITL backend (requires slack_sdk)"""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.token = config.get("slack_token") or os.environ.get("SLACK_BOT_TOKEN")
        self.channel_id = config.get("slack_channel") or os.environ.get("SLACK_CHANNEL_ID")
        self._client = None
        
        if self.token:
            try:
                from slack_sdk import WebClient
                self._client = WebClient(token=self.token)
            except ImportError:
                print("Warning: slack_sdk not installed. Slack backend unavailable.")
    
    def send_request(self, request: ApprovalRequest) -> bool:
        """Send approval request to Slack channel"""
        if not self._client:
            print("Warning: Slack client not configured. Falling back to CLI.")
            return False
        
        try:
            message = f"""
🔔 *Human Approval Required*

**Request ID:** {request.id}
**Timeout:** {request.timeout}s

---
{request.prompt}
---

Reply with:
• `approve {request.id}` - to approve
• `reject {request.id}` - to reject
"""
            
            self._client.chat_postMessage(
                channel=self.channel_id,
                text=message,
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": message
                        }
                    },
                    {
                        "type": "actions",
                        "elements": [
                            {
                                "type": "button",
                                "text": {"type": "plain_text", "text": "Approve"},
                                "action_id": f"approve_{request.id}",
                                "style": "primary"
                            },
                            {
                                "type": "button",
                                "text": {"type": "plain_text", "text": "Reject"},
                                "action_id": f"reject_{request.id}",
                                "style": "danger"
                            }
                        ]
                    }
                ]
            )
            return True
        except Exception as e:
            print(f"Error sending Slack message: {e}")
            return False
    
    def wait_for_response(self, request: ApprovalRequest, timeout: int) -> ApprovalStatus:
        """Wait for Slack response (requires interaction handler)"""
        # Note: Full Slack integration requires an interactive component server
        # For now, fall back to file-based polling
        print("Note: Slack backend requires interactive server. Using file polling...")
        
        file_backend = FileBackend(self.config)
        return file_backend.wait_for_response(request, timeout)
    
    def cancel_request(self, request: ApprovalRequest) -> bool:
        """Cancel Slack request"""
        # Would need to update/delete the Slack message
        return True


class HITLManager:
    """Manager for Human-in-the-Loop operations"""
    
    _instance: Optional['HITLManager'] = None
    
    def __init__(self, default_channel: str = "CLI", config: Dict[str, Any] = None):
        self.default_channel = default_channel
        self.config = config or {}
        self._backends: Dict[str, HITLBackend] = {}
        self._pending_requests: Dict[str, ApprovalRequest] = {}
        
        # Register default backends
        self._register_backend("CLI", CLIBackend(config))
        self._register_backend("file", FileBackend(config))
        self._register_backend("File", FileBackend(config))
        
        # Register Slack if configured
        if os.environ.get("SLACK_BOT_TOKEN"):
            self._register_backend("Slack", SlackBackend(config))
            self._register_backend("slack", SlackBackend(config))
    
    @classmethod
    def get_instance(cls) -> 'HITLManager':
        """Get singleton instance"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def reset_instance(cls):
        """Reset singleton (for testing)"""
        cls._instance = None
    
    def _register_backend(self, name: str, backend: HITLBackend):
        """Register a HITL backend"""
        self._backends[name.lower()] = backend
        self._backends[name] = backend
    
    def _get_backend(self, channel: str) -> HITLBackend:
        """Get backend for channel"""
        backend = self._backends.get(channel) or self._backends.get(channel.lower())
        if not backend:
            print(f"Warning: Unknown channel '{channel}'. Using CLI backend.")
            backend = self._backends["CLI"]
        return backend
    
    def _generate_request_id(self) -> str:
        """Generate unique request ID"""
        import uuid
        return f"hitl_{uuid.uuid4().hex[:8]}"
    
    def wait_for_human(
        self,
        prompt: str,
        channel: Optional[str] = None,
        timeout: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> ApprovalStatus:
        """
        Wait for human approval/input.
        
        Args:
            prompt: The message/prompt to display to the human
            channel: Notification channel (CLI, Slack, Email, File)
            timeout: Timeout in seconds (None = no timeout)
            context: Additional context data to display
            
        Returns:
            ApprovalStatus indicating the result
        """
        channel = channel or self.default_channel
        backend = self._get_backend(channel)
        
        # Create request
        request = ApprovalRequest(
            id=self._generate_request_id(),
            prompt=prompt,
            channel=channel,
            timeout=timeout,
            context=context or {}
        )
        
        # Store pending request
        self._pending_requests[request.id] = request
        
        # Send request
        if not backend.send_request(request):
            # Fallback to CLI if backend fails
            backend = self._backends["CLI"]
            backend.send_request(request)
        
        # Wait for response
        status = backend.wait_for_response(request, timeout or 0)
        request.status = status
        
        # Clean up
        self._pending_requests.pop(request.id, None)
        
        return status
    
    def get_pending_requests(self) -> List[ApprovalRequest]:
        """Get all pending approval requests"""
        return list(self._pending_requests.values())
    
    def cancel_all(self) -> int:
        """Cancel all pending requests. Returns count of cancelled requests."""
        count = 0
        for request_id, request in list(self._pending_requests.items()):
            backend = self._get_backend(request.channel)
            if backend.cancel_request(request):
                request.status = ApprovalStatus.CANCELLED
                count += 1
        self._pending_requests.clear()
        return count


# Global singleton instance
_manager: Optional[HITLManager] = None


def get_hitl_manager() -> HITLManager:
    """Get the global HITL manager instance"""
    global _manager
    if _manager is None:
        _manager = HITLManager()
    return _manager


def wait_for_human(
    prompt: str,
    channel: Optional[str] = None,
    timeout: Optional[int] = None,
    context: Optional[Dict[str, Any]] = None
) -> ApprovalStatus:
    """
    Wait for human approval/input.
    
    This is the main primitive function exposed to Nexa code.
    
    Usage:
        status = wait_for_human("Please approve this action")
        status = wait_for_human("Review plan", channel="Slack", timeout=300)
        
        if status == ApprovalStatus.APPROVED:
            # proceed with action
        elif status == ApprovalStatus.REJECTED:
            # handle rejection
        else:
            # handle timeout or cancellation
    
    Args:
        prompt: The message/prompt to display to the human
        channel: Notification channel (CLI, Slack, Email, File). Default: CLI
        timeout: Timeout in seconds. None means no timeout.
        context: Additional context data to include
        
    Returns:
        ApprovalStatus enum value
    """
    return get_hitl_manager().wait_for_human(prompt, channel, timeout, context)


def approve_request(request_id: str, response: str = None, responder: str = None) -> bool:
    """
    Approve a pending request (for external approval handlers).
    
    Args:
        request_id: The request ID to approve
        response: Optional response message
        responder: Optional responder identity
        
    Returns:
        True if request was found and approved
    """
    manager = get_hitl_manager()
    request = manager._pending_requests.get(request_id)
    if request:
        request.status = ApprovalStatus.APPROVED
        request.response = response
        request.responder = responder
        return True
    return False


def reject_request(request_id: str, response: str = None, responder: str = None) -> bool:
    """
    Reject a pending request (for external approval handlers).
    
    Args:
        request_id: The request ID to reject
        response: Optional response message
        responder: Optional responder identity
        
    Returns:
        True if request was found and rejected
    """
    manager = get_hitl_manager()
    request = manager._pending_requests.get(request_id)
    if request:
        request.status = ApprovalStatus.REJECTED
        request.response = response
        request.responder = responder
        return True
    return False


# Convenience exports
__all__ = [
    'ApprovalStatus',
    'ApprovalRequest',
    'HITLManager',
    'HITLBackend',
    'CLIBackend',
    'FileBackend',
    'SlackBackend',
    'wait_for_human',
    'get_hitl_manager',
    'approve_request',
    'reject_request'
]
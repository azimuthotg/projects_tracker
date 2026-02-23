"""Audit trail helpers — call log_action() from views and signals."""
from __future__ import annotations


def get_client_ip(request) -> str | None:
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR') or None


def log_action(
    actor,           # User instance or None (for anonymous / LOGIN_FAILED)
    action: str,     # One of AuditLog.ACTION_CHOICES keys
    target_repr: str = '',
    detail: str = '',
    ip_address: str | None = None,
    target_user=None,  # User instance being acted upon (user management actions)
) -> None:
    """Create an AuditLog entry. Never raises — errors are silently swallowed."""
    try:
        from .models import AuditLog
        level = AuditLog.ACTION_LEVELS.get(action, AuditLog.LEVEL_IMPORTANT)
        AuditLog.objects.create(
            user=actor if (actor and actor.pk) else None,
            action=action,
            level=level,
            target_repr=target_repr[:500] if target_repr else '',
            detail=detail,
            ip_address=ip_address,
            target_user=target_user,
        )
    except Exception:
        pass

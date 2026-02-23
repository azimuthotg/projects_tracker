"""Django auth signals → AuditLog entries."""
from django.contrib.auth.signals import (
    user_logged_in,
    user_logged_out,
    user_login_failed,
)
from django.dispatch import receiver

from .audit import get_client_ip, log_action


@receiver(user_logged_in)
def on_user_logged_in(sender, request, user, **kwargs):
    log_action(
        actor=user,
        action='LOGIN',
        target_repr=user.username,
        ip_address=get_client_ip(request),
    )


@receiver(user_logged_out)
def on_user_logged_out(sender, request, user, **kwargs):
    if user:
        log_action(
            actor=user,
            action='LOGOUT',
            target_repr=user.username,
            ip_address=get_client_ip(request),
        )


@receiver(user_login_failed)
def on_user_login_failed(sender, credentials, request, **kwargs):
    username = credentials.get('username', '')
    log_action(
        actor=None,
        action='LOGIN_FAILED',
        target_repr=username,
        detail=f'ชื่อผู้ใช้ที่ระบุ: {username}',
        ip_address=get_client_ip(request),
    )

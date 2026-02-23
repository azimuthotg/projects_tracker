"""
NPU Authentication Backend
Authenticates staff via NPU AD/LDAP API with local fallback
"""
import logging

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import BaseBackend
from django.utils import timezone

from .models import ApprovedOrganization, UserProfile
from .npu_api import NPUApiClient, extract_user_data

User = get_user_model()
logger = logging.getLogger(__name__)


class NPUAuthBackend(BaseBackend):
    """
    Authentication flow:
    1. superuser/admin → check local password
    2. manual user (has_usable_password) → check local password
    3. NPU API → create/update User + UserProfile → login
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None

        # Check if local user exists
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            user = None

        # 1. Superuser → always use local password
        if user and user.is_superuser:
            if user.check_password(password):
                return user
            return None

        # 2. NPU AD user (source=npu_api) → always use NPU API
        if user:
            try:
                profile = user.profile
                if profile.source == 'npu_api':
                    return self._authenticate_npu(username, password)
            except UserProfile.DoesNotExist:
                pass

        # 3. Manual user with usable password → local password
        if user and user.has_usable_password():
            if user.check_password(password):
                return user
            return None

        # 4. New user → try NPU API
        return self._authenticate_npu(username, password)

    def _authenticate_npu(self, username, password):
        """Authenticate via NPU Staff API and create/update local user"""
        client = NPUApiClient()
        response = client.authenticate_user(username, password)

        if not response:
            return None

        user_data = extract_user_data(response)
        if not user_data:
            return None

        citizen_id = user_data['citizen_id']
        if not citizen_id:
            logger.error("NPU response missing citizen_id for %s", username)
            return None

        org_name = user_data.get('department_name', '')

        # Check if the user's organization is in the approved list
        is_org_approved = ApprovedOrganization.objects.filter(
            name=org_name, is_active=True
        ).exists()

        # Get or create Django User (username = citizen_id)
        # is_active starts False for new users; we'll set it properly below
        user, created = User.objects.get_or_create(
            username=citizen_id,
            defaults={
                'first_name': user_data['first_name'],
                'last_name': user_data['last_name'],
                'is_active': False,
            },
        )

        # Always update name from NPU
        user.first_name = user_data['first_name']
        user.last_name = user_data['last_name']

        if created:
            user.set_unusable_password()
            user.save(update_fields=['first_name', 'last_name', 'password', 'is_active'])
        else:
            user.save(update_fields=['first_name', 'last_name'])

        # Get or create UserProfile
        profile, _ = UserProfile.objects.get_or_create(
            user=user,
            defaults={'role': 'staff', 'source': 'npu_api'},
        )

        # Update NPU-specific fields
        profile.npu_citizen_id = citizen_id
        profile.npu_staff_id = user_data.get('npu_staff_id', '')
        profile.position_title = user_data.get('position_title', '')
        profile.employment_status = user_data.get('employment_status', '')
        profile.organization = org_name
        profile.source = 'npu_api'
        profile.last_npu_sync = user_data['last_npu_sync']

        # --- Approval logic ---
        if profile.approval_status == 'rejected':
            # Admin explicitly rejected — never auto-approve
            pass
        elif is_org_approved:
            # Org is approved → activate (covers both new and pending users)
            user.is_active = True
            user.save(update_fields=['is_active'])
            profile.approval_status = 'approved'
        elif created:
            # New user from non-approved org → pending
            profile.approval_status = 'pending'
            logger.info("New NPU user from unapproved org, set to pending: %s (%s)", citizen_id, org_name)
        # else: existing approved user from org that was later removed → keep approved

        # แผนก (department) → admin เลือกให้ทีหลัง ไม่ auto-match จาก AD
        profile.save()

        if created:
            logger.info("Created new NPU user: %s (%s %s)", citizen_id, user.first_name, user.last_name)
        else:
            logger.info("Updated NPU user: %s", citizen_id)

        return user

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None

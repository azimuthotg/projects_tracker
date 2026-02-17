"""
NPU API Integration Module
Handles communication with NPU AD/LDAP API for staff authentication
"""
import logging
import time

import requests
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


class NPUApiClient:
    """Client for NPU AD/LDAP API"""

    def __init__(self):
        npu = settings.NPU_API_SETTINGS
        self.base_url = npu['base_url']
        self.auth_endpoint = npu['auth_endpoint']
        self.token = npu['token']
        self.timeout = npu['timeout']

    def authenticate_user(self, ldap_uid, password):
        """
        Authenticate user with NPU Staff API

        Args:
            ldap_uid: รหัสบัตรประชาชน 13 หลัก หรือ username
            password: รหัสผ่าน

        Returns:
            dict: API response or None on failure
        """
        url = f"{self.base_url}{self.auth_endpoint}"
        payload = {"userLdap": ldap_uid, "passLdap": password}
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
        }

        start = time.time()
        try:
            response = requests.post(
                url, json=payload, headers=headers, timeout=self.timeout
            )
            elapsed_ms = int((time.time() - start) * 1000)

            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    logger.info("NPU auth success for %s (%dms)", ldap_uid, elapsed_ms)
                    return data
                else:
                    logger.warning("NPU auth failed for %s: invalid credentials (%dms)", ldap_uid, elapsed_ms)
                    return None
            else:
                logger.error("NPU API HTTP %d for %s (%dms)", response.status_code, ldap_uid, elapsed_ms)
                return None

        except requests.exceptions.Timeout:
            logger.error("NPU API timeout for %s after %ds", ldap_uid, self.timeout)
            return None
        except requests.exceptions.ConnectionError:
            logger.error("NPU API connection error for %s", ldap_uid)
            return None
        except Exception as e:
            logger.exception("NPU API unexpected error for %s: %s", ldap_uid, e)
            return None


def extract_user_data(npu_response):
    """
    Extract and format user data from NPU API response

    Returns:
        dict with keys: citizen_id, npu_staff_id, first_name, last_name,
                        department_name, position_title, last_npu_sync
    """
    if not npu_response or not npu_response.get('success'):
        return None

    info = npu_response.get('personnel_info', {})

    return {
        'citizen_id': info.get('staffcitizenid', ''),
        'npu_staff_id': info.get('staffid', ''),
        'first_name': info.get('staffname', ''),
        'last_name': info.get('staffsurname', ''),
        'department_name': info.get('departmentname', ''),
        'position_title': info.get('posnameth', ''),
        'employment_status': info.get('stfstaname', ''),
        'last_npu_sync': timezone.now(),
    }

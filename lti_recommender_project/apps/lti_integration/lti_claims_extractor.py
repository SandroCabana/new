"""
LTI Claims Extractor — v2
Mapea todos los claims LTI 1.3 relevantes a un dict normalizado.
Utilizado en lti_launch para construir el StudentProfile.
"""
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)

# LTI 1.3 claim namespaces
LTI_CLAIM_NS = "https://purl.imsglobal.org/spec/lti/claim"
NRPS_CLAIM_NS = "https://purl.imsglobal.org/spec/lti-nrps/claim"
AGS_CLAIM_NS = "https://purl.imsglobal.org/spec/lti-ags/claim"

# LTI role URNs
INSTRUCTOR_ROLES = {
    'http://purl.imsglobal.org/vocab/lis/v2/membership#Instructor',
    'http://purl.imsglobal.org/vocab/lis/v2/membership#TeachingAssistant',
    'http://purl.imsglobal.org/vocab/lis/v2/institution/person#Instructor',
    'http://purl.imsglobal.org/vocab/lis/v2/institution/person#Administrator',
    'Instructor',  # Short form sometimes sent by Moodle
}


class LTIClaimsExtractor:
    """
    Extrae y normaliza todos los claims LTI 1.3 relevantes para personalización.
    
    Claims cubiertos:
    - Identity: sub, name, email, locale
    - Context: course id, title, type
    - Roles: membership roles → is_instructor flag
    - Resource Link: specific activity context
    - Tool Platform: Moodle version/name
    - Custom claims: subject, level, career (configurables en Moodle)
    - LTI Advantage: NRPS endpoint, AGS endpoint
    """

    @classmethod
    def extract_all(cls, launch_data: dict) -> Dict[str, Any]:
        """
        Extrae perfil completo desde LTI launch_data.
        
        Args:
            launch_data: dict del JWT de lanzamiento LTI validado por PyLTI1p3
        
        Returns:
            Dict normalizado con todos los claims relevantes
        """
        roles = cls._get_claim(launch_data, 'roles', default=[])

        return {
            # ── Identity ──────────────────────────────────────────────
            'user_id': launch_data.get('sub', 'N/A'),
            'name': launch_data.get('name', 'N/A'),
            'given_name': launch_data.get('given_name', ''),
            'family_name': launch_data.get('family_name', ''),
            'email': launch_data.get('email', ''),
            'locale': launch_data.get('locale', 'es'),
            'issuer': launch_data.get('iss', 'unknown_issuer'),

            # ── Context (Curso) ────────────────────────────────────────
            'context_id': cls._get_nested(launch_data, 'context', 'id', default='N/A'),
            'context_title': cls._get_nested(launch_data, 'context', 'title', default='N/A'),
            'context_type': cls._get_nested(launch_data, 'context', 'type', default=[]),
            'context_label': cls._get_nested(launch_data, 'context', 'label', default=''),

            # ── Roles ──────────────────────────────────────────────────
            'roles': roles,
            'is_instructor': cls._is_instructor(roles),
            'is_student': cls._is_student(roles),

            # ── Resource Link (actividad específica) ───────────────────
            'resource_link_id': cls._get_nested(launch_data, 'resource_link', 'id', default=''),
            'resource_link_title': cls._get_nested(launch_data, 'resource_link', 'title', default=''),
            'resource_link_description': cls._get_nested(
                launch_data, 'resource_link', 'description', default=''
            ),

            # ── Tool Platform (Moodle) ─────────────────────────────────
            'platform_guid': cls._get_nested(launch_data, 'tool_platform', 'guid', default=''),
            'platform_name': cls._get_nested(launch_data, 'tool_platform', 'name', default='N/A'),
            'platform_version': cls._get_nested(
                launch_data, 'tool_platform', 'version', default=''
            ),

            # ── Custom claims (configurables en Moodle) ────────────────
            # Para usar: agregar en Moodle → External Tool → Custom Parameters:
            #   subject=$$CourseSection.subject
            #   level=$$People.sourced_id
            #   career=custom_career
            'custom_subject': cls._get_custom(launch_data, 'subject'),
            'custom_level': cls._get_custom(launch_data, 'level'),
            'custom_career': cls._get_custom(launch_data, 'career'),

            # ── LTI Advantage Services ─────────────────────────────────
            'nrps_endpoint': cls._get_nrps_endpoint(launch_data),
            'ags_lineitem': cls._get_ags_lineitem(launch_data),

            # ── Deployment ─────────────────────────────────────────────
            'deployment_id': cls._get_claim(launch_data, 'deployment_id', default=''),
        }

    # ── Private helpers ────────────────────────────────────────────────────

    @classmethod
    def _get_claim(cls, data: dict, claim: str, default=None):
        """Obtiene un claim LTI por nombre corto (con namespace)."""
        namespaced = f"{LTI_CLAIM_NS}/{claim}"
        return data.get(namespaced, data.get(claim, default))

    @classmethod
    def _get_nested(cls, data: dict, claim: str, key: str, default=None):
        """Obtiene un subclaim de un claim LTI anidado."""
        claim_obj = cls._get_claim(data, claim, default={})
        if not isinstance(claim_obj, dict):
            return default
        return claim_obj.get(key, default)

    @classmethod
    def _get_custom(cls, data: dict, key: str) -> Optional[str]:
        """Obtiene un custom claim configurado en Moodle."""
        custom = cls._get_claim(data, 'custom', default={})
        return custom.get(key) if isinstance(custom, dict) else None

    @classmethod
    def _get_nrps_endpoint(cls, data: dict) -> Optional[str]:
        """Obtiene el endpoint NRPS si está disponible."""
        nrps_claim = f"{NRPS_CLAIM_NS}/namesroleservice"
        nrps = data.get(nrps_claim, {})
        return nrps.get('context_memberships_url') if isinstance(nrps, dict) else None

    @classmethod
    def _get_ags_lineitem(cls, data: dict) -> Optional[str]:
        """Obtiene el endpoint AGS si está disponible."""
        ags_claim = f"{AGS_CLAIM_NS}/endpoint"
        ags = data.get(ags_claim, {})
        return ags.get('lineitem') if isinstance(ags, dict) else None

    @classmethod
    def _is_instructor(cls, roles: List[str]) -> bool:
        """Determina si el usuario es instructor/docente."""
        return bool(set(roles) & INSTRUCTOR_ROLES)

    @classmethod
    def _is_student(cls, roles: List[str]) -> bool:
        """Determina si el usuario es estudiante."""
        student_indicators = {
            'http://purl.imsglobal.org/vocab/lis/v2/membership#Learner',
            'Learner', 'Student',
        }
        return bool(set(roles) & student_indicators) or not cls._is_instructor(roles)

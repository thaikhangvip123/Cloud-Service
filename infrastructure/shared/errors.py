"""Application errors with stable API error codes."""


class PortalError(Exception):
    code = "INTERNAL_ERROR"
    status_code = 500


class ValidationError(PortalError):
    code = "VALIDATION_ERROR"
    status_code = 400


class AuthenticationError(PortalError):
    code = "AUTHENTICATION_FAILED"
    status_code = 401


class DurationExceededError(ValidationError):
    code = "DURATION_EXCEEDED"


class GroupMappingNotFoundError(PortalError):
    code = "GROUP_MAPPING_NOT_FOUND"
    status_code = 404


class UserNotFoundError(PortalError):
    code = "USER_NOT_FOUND"
    status_code = 404


class IdentityCenterError(PortalError):
    code = "IDENTITY_CENTER_ERROR"


class AmbiguousIdentityError(IdentityCenterError):
    code = "AMBIGUOUS_IDENTITY"
    status_code = 409


class MembershipConflictError(IdentityCenterError):
    code = "MEMBERSHIP_CONFLICT"
    status_code = 409


class EmergencyRevocationError(IdentityCenterError):
    code = "EMERGENCY_REVOCATION_FAILED"


class LegacySessionError(IdentityCenterError):
    code = "LEGACY_SESSION_REVOKE_UNAVAILABLE"


class SchedulingError(PortalError):
    code = "EXPIRY_SCHEDULING_FAILED"


class DynamoDBError(PortalError):
    code = "DYNAMODB_ERROR"


class JiraUpdateError(PortalError):
    code = "JIRA_UPDATE_ERROR"


class TokenValidationError(AuthenticationError):
    code = "TOKEN_VALIDATION_FAILED"


class TokenAlreadyUsedError(TokenValidationError):
    code = "TOKEN_ALREADY_USED"
    status_code = 409

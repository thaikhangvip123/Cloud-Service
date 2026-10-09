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


class DynamoDBError(PortalError):
    code = "DYNAMODB_ERROR"


class JiraUpdateError(PortalError):
    code = "JIRA_UPDATE_ERROR"


class TokenValidationError(AuthenticationError):
    code = "TOKEN_VALIDATION_FAILED"


class TokenAlreadyUsedError(TokenValidationError):
    code = "TOKEN_ALREADY_USED"
    status_code = 409

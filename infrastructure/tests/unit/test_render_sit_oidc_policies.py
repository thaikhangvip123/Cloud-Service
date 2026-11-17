import json
import re
from pathlib import Path

import pytest

from scripts.render_sit_oidc_policies import (
    ACCOUNT_ID_PLACEHOLDER,
    IDENTITY_STORE_ID_PLACEHOLDER,
    INSTANCE_ID_PLACEHOLDER,
    POLICY_SIZE_LIMIT,
    SAML_PROVIDER_ARN_PLACEHOLDER,
    TARGET_ACCOUNT_ARNS_PLACEHOLDER,
    TARGET_ADMIN_SSO_ROLE_ARNS_PLACEHOLDER,
    TARGET_POWERUSER_SSO_ROLE_ARNS_PLACEHOLDER,
    TARGET_READONLY_SSO_ROLE_ARNS_PLACEHOLDER,
    TARGET_SSO_ROLE_ARNS_PLACEHOLDER,
    compact_policy_size,
    render_policy,
    render_templates,
)


TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "iam" / "github-actions"
SIT_BACKEND_CONFIG = Path(__file__).resolve().parents[2] / "terraform" / "backend" / "sit.hcl"
RENDER_ARGS = (
    "123456789012",
    "ssoins-1234567890abcdef",
    "d-1234567890",
    "arn:aws:iam::123456789012:saml-provider/AWSSSO_1234567890abcdef_DO_NOT_DELETE",
    ["123456789012"],
)


def statements(policy):
    return policy["Statement"]


def actions(policy):
    result = set()
    for statement in statements(policy):
        value = statement["Action"]
        result.update(value if isinstance(value, list) else [value])
    return result


def statement(policy, sid):
    return next(item for item in statements(policy) if item["Sid"] == sid)


def rendered(template_name):
    return render_policy(TEMPLATE_DIR / template_name, *RENDER_ARGS)


def sit_state_bucket():
    match = re.search(
        r'^bucket\s*=\s*"([^"]+)"$',
        SIT_BACKEND_CONFIG.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    assert match is not None
    return match.group(1)


def test_render_templates_produces_valid_size_limited_json(tmp_path):
    outputs = render_templates(TEMPLATE_DIR, tmp_path, *RENDER_ARGS)

    assert len(outputs) == 6
    placeholders = (
        ACCOUNT_ID_PLACEHOLDER,
        INSTANCE_ID_PLACEHOLDER,
        IDENTITY_STORE_ID_PLACEHOLDER,
        SAML_PROVIDER_ARN_PLACEHOLDER,
        TARGET_ACCOUNT_ARNS_PLACEHOLDER,
        TARGET_SSO_ROLE_ARNS_PLACEHOLDER,
        TARGET_READONLY_SSO_ROLE_ARNS_PLACEHOLDER,
        TARGET_POWERUSER_SSO_ROLE_ARNS_PLACEHOLDER,
        TARGET_ADMIN_SSO_ROLE_ARNS_PLACEHOLDER,
    )
    for output in outputs:
        content = output.read_text(encoding="utf-8")
        policy = json.loads(content)
        assert not any(item in content for item in placeholders)
        assert compact_policy_size(policy) <= POLICY_SIZE_LIMIT


def test_plan_policies_cannot_modify_stack_resources():
    plan_actions = actions(rendered("sit-backend-plan-policy.template.json"))
    plan_actions |= actions(rendered("sit-resource-read-policy.template.json"))

    assert "iam:CreateRole" not in plan_actions
    assert "lambda:CreateFunction" not in plan_actions
    assert "dynamodb:CreateTable" not in plan_actions
    assert "s3:PutObject" not in plan_actions
    assert {"dynamodb:PutItem", "dynamodb:DeleteItem"} <= plan_actions


@pytest.mark.parametrize(
    ("template_name", "state_sid"),
    [
        ("sit-backend-plan-policy.template.json", "ReadSitState"),
        ("sit-backend-apply-policy.template.json", "ReadWriteSitState"),
    ],
)
def test_backend_policies_target_bootstrapped_sit_bucket(template_name, state_sid):
    policy = rendered(template_name)
    bucket = sit_state_bucket()

    assert statement(policy, "ListSitStatePrefix")["Resource"] == (f"arn:aws:s3:::{bucket}")
    assert statement(policy, state_sid)["Resource"] == (
        f"arn:aws:s3:::{bucket}/production-access-portal/sit/terraform.tfstate"
    )


def test_apply_iam_policy_never_targets_deployment_roles():
    policy = rendered("sit-apply-iam-lambda-policy.template.json")
    resources = json.dumps(policy)

    assert "pa-sit-github-plan" not in resources
    assert "pa-sit-github-apply" not in resources
    assert "role/pa-sit-*" not in resources
    assert "iam:PassRole" in actions(policy)


def test_apply_policy_manages_only_expected_scheduler_and_api_roles():
    policy = rendered("sit-apply-iam-lambda-policy.template.json")
    manage_roles = statement(policy, "ManageLambdaExecutionRoles")
    managed_roles = statement(policy, "ManageLambdaExecutionRoles")["Resource"]
    api_pass_role = statement(policy, "PassApiGatewayCloudWatchRole")

    assert "iam:CreateRole" in manage_roles["Action"]
    assert set(managed_roles) == {
        "arn:aws:iam::123456789012:role/pa-sit-executor-role-ap-southeast-1",
        "arn:aws:iam::123456789012:role/pa-sit-expiry-role-ap-southeast-1",
        "arn:aws:iam::123456789012:role/pa-sit-email-approval-role-ap-southeast-1",
        "arn:aws:iam::123456789012:role/pa-sit-expiry-scheduler-role-ap-southeast-1",
        "arn:aws:iam::123456789012:role/pa-sit-api-cloudwatch-role-ap-southeast-1",
    }
    assert api_pass_role["Resource"] == (
        "arn:aws:iam::123456789012:role/pa-sit-api-cloudwatch-role-ap-southeast-1"
    )
    assert api_pass_role["Condition"]["StringEquals"]["iam:PassedToService"] == (
        "apigateway.amazonaws.com"
    )


def test_scheduler_and_api_logging_permissions_are_environment_scoped():
    apply_policy = rendered("sit-apply-edge-observability-policy.template.json")
    read_policy = rendered("sit-resource-read-policy.template.json")

    schedule_group_arn = (
        "arn:aws:scheduler:ap-southeast-1:123456789012:"
        "schedule-group/pa-sit-expiry-ap-southeast-1"
    )
    assert statement(apply_policy, "ManageSitExpiryScheduleGroup")["Resource"] == (
        schedule_group_arn
    )
    assert statement(read_policy, "ReadSitExpiryScheduleGroup")["Resource"] == (schedule_group_arn)
    log_resources = statement(apply_policy, "ManageSitApplicationLogs")["Resource"]
    assert any("log-group:/aws/apigateway/pa-sit-*" in item for item in log_resources)
    assert (
        "arn:aws:apigateway:ap-southeast-1::/account"
        in statement(apply_policy, "ManageSitApiGateway")["Resource"]
    )


def test_identity_center_writes_are_scoped_to_sit_inputs():
    policy = rendered("sit-apply-data-identity-policy.template.json")
    assignment = statement(policy, "ManageSitAccountAssignments")
    resources = assignment["Resource"]

    assert "arn:aws:sso:::instance/ssoins-1234567890abcdef" in resources
    assert "arn:aws:sso:::permissionSet/ssoins-1234567890abcdef/*" in resources
    assert "arn:aws:sso:::account/123456789012" in resources
    assert "*" not in resources


def test_apply_policy_reads_exact_identity_center_saml_provider():
    policy = rendered("sit-apply-data-identity-policy.template.json")
    saml_provider = statement(policy, "ReadIdentityCenterSamlProvider")

    assert saml_provider["Action"] == "iam:GetSAMLProvider"
    assert saml_provider["Resource"] == RENDER_ARGS[3]
    assert "saml-provider/arn:" not in saml_provider["Resource"]


def test_apply_policy_limits_identity_center_provisioned_roles():
    policy = rendered("sit-apply-data-identity-policy.template.json")
    manage = statement(policy, "ManageIdentityCenterProvisionedRoles")
    readonly = statement(policy, "AttachReadOnlyIdentityCenterManagedPolicy")
    power_user = statement(policy, "AttachPowerUserIdentityCenterManagedPolicy")
    admin = statement(policy, "AttachAdminIdentityCenterManagedPolicy")
    expected_role = (
        "arn:aws:iam::123456789012:role/aws-reserved/sso.amazonaws.com/"
        "ap-southeast-1/AWSReservedSSO_pa-sit-*"
    )

    assert manage["Resource"] == [expected_role]
    assert {
        "iam:CreateRole",
        "iam:UpdateRole",
        "iam:UpdateAssumeRolePolicy",
    } <= set(manage["Action"])
    assert "iam:PutRolePolicy" not in manage["Action"]
    assert readonly["Resource"] == [expected_role.replace("pa-sit-*", "pa-sit-ReadOnly-*")]
    assert readonly["Condition"]["ArnEquals"]["iam:PolicyARN"] == (
        "arn:aws:iam::aws:policy/ReadOnlyAccess"
    )
    assert power_user["Resource"] == [
        expected_role.replace("pa-sit-*", "pa-sit-PowerUser-*")
    ]
    assert power_user["Condition"]["ArnEquals"]["iam:PolicyARN"] == (
        "arn:aws:iam::aws:policy/PowerUserAccess"
    )
    assert admin["Resource"] == [expected_role.replace("pa-sit-*", "pa-sit-Admin-*")]
    assert admin["Condition"]["ArnEquals"]["iam:PolicyARN"] == (
        "arn:aws:iam::aws:policy/AdministratorAccess"
    )


def test_event_source_mapping_creation_is_limited_to_expiry_function():
    policy = rendered("sit-apply-iam-lambda-policy.template.json")
    create = statement(policy, "CreateExpiryEventSourceMapping")

    assert create["Resource"] == "*"
    assert create["Condition"]["ArnEquals"]["lambda:FunctionArn"].endswith(
        ":function:pa-sit-expiry-ap-southeast-1"
    )


def test_confirmed_invalid_s3_actions_are_absent():
    invalid = {
        "s3:DeleteBucketPublicAccessBlock",
        "s3:DeleteEncryptionConfiguration",
        "s3:DeleteBucketTagging",
    }

    for template in TEMPLATE_DIR.glob("*.template.json"):
        assert actions(render_policy(template, *RENDER_ARGS)).isdisjoint(invalid)


def test_policies_do_not_use_service_wide_actions():
    for template in TEMPLATE_DIR.glob("*.template.json"):
        policy = render_policy(template, *RENDER_ARGS)
        assert not any(action.endswith(":*") for action in actions(policy))


@pytest.mark.parametrize(
    "account_id",
    [
        "not-an-account",
        "\uff11\uff12\uff13\uff14\uff15\uff16\uff17\uff18\uff19\uff10\uff11\uff12",
    ],
)
def test_render_policy_rejects_invalid_account_id(account_id):
    template = TEMPLATE_DIR / "sit-backend-plan-policy.template.json"

    with pytest.raises(ValueError, match="12 ASCII digits"):
        render_policy(template, account_id, *RENDER_ARGS[1:])


def test_render_policy_rejects_invalid_identity_center_inputs():
    template = TEMPLATE_DIR / "sit-resource-read-policy.template.json"

    with pytest.raises(ValueError, match="instance ID"):
        render_policy(
            template,
            RENDER_ARGS[0],
            "invalid-instance",
            RENDER_ARGS[2],
            RENDER_ARGS[3],
            RENDER_ARGS[4],
        )
    with pytest.raises(ValueError, match="Identity Store ID"):
        render_policy(
            template,
            RENDER_ARGS[0],
            RENDER_ARGS[1],
            "bad",
            RENDER_ARGS[3],
            RENDER_ARGS[4],
        )


def test_render_policy_rejects_saml_provider_from_another_account():
    template = TEMPLATE_DIR / "sit-apply-data-identity-policy.template.json"

    with pytest.raises(ValueError, match="deployment AWS account"):
        render_policy(
            template,
            RENDER_ARGS[0],
            RENDER_ARGS[1],
            RENDER_ARGS[2],
            "arn:aws:iam::210987654321:"
            "saml-provider/AWSSSO_1234567890abcdef_DO_NOT_DELETE",
            RENDER_ARGS[4],
        )

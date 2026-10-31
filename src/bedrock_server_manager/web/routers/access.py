"""Manage named credentials and explicit account/server restrictions."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, Security

from ...context import AppContext
from ..access_policy import ROLE_GRANTS, Permission, policy_for
from ..authorization import (
    NON_DELEGATABLE,
    SERVER_PERMISSIONS,
    current_authorization,
    server_collection,
)
from ..deps import get_app_context
from ..deps.auth import require_permissions
from ..schemas import BaseApiResponse, UserResponse
from ..schemas.access import (
    AccessPolicyInfo,
    AccessServerInfo,
    AccountServerAccessInfo,
    CreatedIntegrationToken,
    CreateIntegrationToken,
    IntegrationTokenInfo,
    SetServerAccess,
)


def no_store(response: Response):
    response.headers["Cache-Control"] = "no-store"


router = APIRouter(tags=["Access Management"], dependencies=[Depends(no_store)])


@router.get(
    "/api/access/policy",
    operation_id="get_access_policy",
    response_model=AccessPolicyInfo,
)
async def get_access_policy(
    request: Request,
    user: UserResponse = Security(
        require_permissions, scopes=[Permission.ACCOUNT_READ]
    ),
):
    policy = policy_for(request)
    authorization = current_authorization.get()
    return AccessPolicyInfo(
        revision=authorization.revision if authorization else policy.revision,
        permissions=policy.descriptions,
        server_permissions=sorted(SERVER_PERMISSIONS),
        token_permissions=sorted(
            (authorization.permissions if authorization else policy.resolve(user.role))
            - NON_DELEGATABLE
        ),
        role_permissions={role: sorted(policy.resolve(role)) for role in ROLE_GRANTS},
    )


@router.get(
    "/api/access/servers",
    operation_id="list_access_servers",
    response_model=list[AccessServerInfo],
)
@server_collection
async def list_access_servers(
    user: UserResponse = Security(
        require_permissions, scopes=[Permission.SERVERS_READ]
    ),
    context: AppContext = Depends(get_app_context),
):
    authorization = current_authorization.get()
    if authorization is None:
        raise HTTPException(401, "Not authenticated")
    servers = (
        authorization.servers
        if authorization.resource_restricted
        else await context.access_service.server_identities()
    )
    return [
        AccessServerInfo(
            id=identity,
            name=name,
            permissions=sorted(
                permission
                for permission in SERVER_PERMISSIONS
                if authorization.allows(permission, name)
            ),
        )
        for name, identity in sorted(servers.items())
        if authorization.allows("servers:read", name)
    ]


@router.get(
    "/api/account/tokens",
    operation_id="list_integration_tokens",
    response_model=list[IntegrationTokenInfo],
)
async def list_tokens(
    user: UserResponse = Security(
        require_permissions, scopes=[Permission.TOKENS_MANAGE]
    ),
    context: AppContext = Depends(get_app_context),
):
    return await context.access_service.list_tokens(user.id)


@router.post(
    "/api/account/tokens",
    operation_id="create_integration_token",
    response_model=CreatedIntegrationToken,
    status_code=201,
)
async def create_token(
    payload: CreateIntegrationToken,
    user: UserResponse = Security(
        require_permissions, scopes=[Permission.TOKENS_MANAGE]
    ),
    context: AppContext = Depends(get_app_context),
):
    return await context.access_service.create_token(user, payload)


@router.delete(
    "/api/account/tokens/{token_id}",
    operation_id="revoke_integration_token",
    response_model=BaseApiResponse,
)
async def revoke_token(
    token_id: str,
    user: UserResponse = Security(
        require_permissions, scopes=[Permission.TOKENS_MANAGE]
    ),
    context: AppContext = Depends(get_app_context),
):
    await context.access_service.revoke_token(user, user.id, token_id)
    return BaseApiResponse(status="success", message="Credential revoked")


@router.get(
    "/api/access/users/{user_id}/servers",
    operation_id="get_account_server_access",
    response_model=AccountServerAccessInfo,
)
async def get_server_access(
    user_id: int,
    user: UserResponse = Security(
        require_permissions, scopes=[Permission.ACCESS_MANAGE]
    ),
    context: AppContext = Depends(get_app_context),
):
    return await context.access_service.get_server_access(user_id)


@router.put(
    "/api/access/users/{user_id}/servers",
    operation_id="set_account_server_access",
    response_model=AccountServerAccessInfo,
)
async def set_server_access(
    user_id: int,
    payload: SetServerAccess,
    user: UserResponse = Security(
        require_permissions, scopes=[Permission.ACCESS_MANAGE]
    ),
    context: AppContext = Depends(get_app_context),
):
    return await context.access_service.set_server_access(user, user_id, payload)


@router.get(
    "/api/access/users/{user_id}/tokens",
    operation_id="list_account_integration_tokens",
    response_model=list[IntegrationTokenInfo],
)
async def list_user_tokens(
    user_id: int,
    user: UserResponse = Security(
        require_permissions, scopes=[Permission.ACCESS_MANAGE]
    ),
    context: AppContext = Depends(get_app_context),
):
    return await context.access_service.list_tokens(user_id)


@router.delete(
    "/api/access/users/{user_id}/tokens/{token_id}",
    operation_id="revoke_account_integration_token",
    response_model=BaseApiResponse,
)
async def revoke_user_token(
    user_id: int,
    token_id: str,
    user: UserResponse = Security(
        require_permissions, scopes=[Permission.ACCESS_MANAGE]
    ),
    context: AppContext = Depends(get_app_context),
):
    await context.access_service.revoke_token(user, user_id, token_id)
    return BaseApiResponse(status="success", message="Credential revoked")

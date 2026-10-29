"""Identity HTTP routes. Routers do not touch the database session directly."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response

from supplymind.api.cookies import clear_session_cookie, set_session_cookie
from supplymind.api.deps import (
    Auth,
    Db,
    client_ip,
    current_request_id,
    limit_login,
    limit_password_reset,
    limit_signup,
    require_csrf,
    session_cookie_value,
)
from supplymind.api.schemas import error_responses
from supplymind.modules.identity.schemas import (
    AuthResponse,
    CsrfResponse,
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RegisterRequest,
    UserView,
    WorkspaceView,
)
from supplymind.modules.identity.service import AuthResult, IdentityService

public_router = APIRouter()
protected_router = APIRouter(dependencies=[Depends(require_csrf)])


def _service(request: Request, db: Db) -> IdentityService:
    return IdentityService(db, request.app.state.clock, request.app.state.settings)


def _auth_response(result: AuthResult) -> AuthResponse:
    return AuthResponse(
        user=UserView(id=result.user_id, email=result.email),
        workspace=WorkspaceView(
            id=result.workspace_id,
            name=result.workspace_name,
            industry=result.industry,
            size_band=result.size_band,
            timezone=result.timezone,
            currency=result.currency,
            onboarding_step=result.onboarding_step,
            onboarding_completed_at=result.onboarding_completed_at,
        ),
        csrf_token=result.csrf_token,
    )


@public_router.post(
    "/auth/register",
    status_code=201,
    response_model=AuthResponse,
    dependencies=[Depends(limit_signup)],
    responses=error_responses(409, 422, 429),
)
def register_account(
    body: RegisterRequest,
    request: Request,
    response: Response,
    db: Db,
) -> AuthResponse:
    result = _service(request, db).register(
        email=body.email,
        password=body.password.get_secret_value(),
        workspace_name=body.workspace_name,
        user_agent=request.headers.get("user-agent"),
        ip=client_ip(request),
        request_id=current_request_id(request),
        presented_session_token=session_cookie_value(request),
    )
    set_session_cookie(response, request.app.state.settings, result.session_token)
    return _auth_response(result)


@public_router.post(
    "/auth/login",
    response_model=AuthResponse,
    dependencies=[Depends(limit_login)],
    responses=error_responses(401, 422, 429),
)
def login_account(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: Db,
) -> AuthResponse:
    result = _service(request, db).login(
        email=body.email,
        password=body.password.get_secret_value(),
        user_agent=request.headers.get("user-agent"),
        ip=client_ip(request),
        request_id=current_request_id(request),
        presented_session_token=session_cookie_value(request),
    )
    set_session_cookie(response, request.app.state.settings, result.session_token)
    return _auth_response(result)


@public_router.post(
    "/auth/password-resets",
    status_code=204,
    response_model=None,
    dependencies=[Depends(limit_password_reset)],
    responses=error_responses(422, 429),
)
def request_password_reset(body: PasswordResetRequest, request: Request, db: Db) -> Response:
    # The token is for a future mailer. It is not written to the response.
    _service(request, db).prepare_password_reset(
        email=body.email,
        request_id=current_request_id(request),
    )
    return Response(status_code=204)


@public_router.post(
    "/auth/password-resets/confirm",
    status_code=204,
    response_model=None,
    dependencies=[Depends(limit_password_reset)],
    responses=error_responses(400, 422, 429),
)
def confirm_password_reset(body: PasswordResetConfirm, request: Request, db: Db) -> Response:
    _service(request, db).confirm_password_reset(
        token=body.token,
        password=body.password.get_secret_value(),
        request_id=current_request_id(request),
    )
    return Response(status_code=204)


@protected_router.post(
    "/auth/logout",
    status_code=204,
    response_model=None,
    responses=error_responses(401, 403),
)
def logout_account(request: Request, auth: Auth, db: Db) -> Response:
    _service(request, db).logout(
        session_id=auth.session_id,
        user_id=auth.user_id,
        workspace_id=auth.workspace_id,
        request_id=current_request_id(request),
    )
    outgoing = Response(status_code=204)
    clear_session_cookie(outgoing, request.app.state.settings)
    return outgoing


@protected_router.post(
    "/auth/sessions/revoke",
    status_code=204,
    response_model=None,
    responses=error_responses(401, 403),
)
def revoke_sessions(request: Request, auth: Auth, db: Db) -> Response:
    _service(request, db).revoke_all_sessions(
        user_id=auth.user_id,
        workspace_id=auth.workspace_id,
        request_id=current_request_id(request),
    )
    outgoing = Response(status_code=204)
    clear_session_cookie(outgoing, request.app.state.settings)
    return outgoing


@protected_router.get("/auth/me", response_model=UserView, responses=error_responses(401, 403))
def read_current_user(auth: Auth) -> UserView:
    return UserView(id=auth.user_id, email=auth.email)


@protected_router.get(
    "/auth/csrf",
    response_model=CsrfResponse,
    responses=error_responses(401, 403),
)
def read_csrf_token(request: Request, auth: Auth, db: Db) -> CsrfResponse:
    token = _service(request, db).rotate_csrf(auth.session_id)
    return CsrfResponse(csrf_token=token)

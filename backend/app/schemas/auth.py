from pydantic import BaseModel, ConfigDict, Field


class TokenResponse(BaseModel):
    username: str
    is_github_user: bool = False


class UserResponse(BaseModel):
    username: str
    email: str | None = None

    model_config = ConfigDict(from_attributes=True)


class GitHubCallbackRequest(BaseModel):
    code: str = Field(min_length=1)
    state: str = Field(min_length=1)


class GitHubLoginUrlResponse(BaseModel):
    """GitHub OAuth 認可 URL と CSRF 検証用 state を返すレスポンス。

    state はフロントが sessionStorage に保持し、コールバック時に CSRF 検証する。
    """

    authorization_url: str
    state: str

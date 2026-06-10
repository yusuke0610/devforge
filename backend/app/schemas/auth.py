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

    state はサーバー側で HttpOnly Cookie に保存され、コールバックで照合される（正本）。
    レスポンスの state はフロントの sessionStorage 照合（多層防御）にも併用する。
    """

    authorization_url: str
    state: str

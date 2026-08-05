# サードパーティライセンス / 使用 OSS

DevForge は多くのオープンソースソフトウェア（OSS）に支えられています。
本ファイルは DevForge が **直接依存している** OSS の一覧と、それぞれのライセンス・
配布元へのリンクをまとめたものです（謝辞および attribution を兼ねます）。

- ここに列挙した各 OSS の著作権・権利は、それぞれの著作権者に帰属します。
- 一覧は直接依存（自分で選んで導入したライブラリ）が対象です。推移的依存は含みません。
- ライセンス種別は各パッケージのメタデータから自動収集しています（手書きの推測ではありません）。
- **依存を追加・更新したら `make licenses` で本ファイルを再生成してください。** 手動編集は不要です。

> 注: 本ファイルは依存 OSS のライセンス表記であり、DevForge 本体のライセンスを定めるものではありません。

## Frontend（ランタイム / バンドルに同梱）

| ライブラリ | バージョン | ライセンス |
|---|---|---|
| [@reduxjs/toolkit](https://redux-toolkit.js.org) | 2.12.0 | MIT |
| [dompurify](https://github.com/cure53/DOMPurify) | 3.4.12 | (MPL-2.0 OR Apache-2.0) |
| [marked](https://marked.js.org) | 18.0.7 | MIT |
| [react](https://react.dev/) | 19.2.8 | MIT |
| [react-dom](https://react.dev/) | 19.2.8 | MIT |
| [react-pdf](https://github.com/wojtekmaj/react-pdf) | 10.4.1 | MIT |
| [react-redux](https://github.com/reduxjs/react-redux) | 9.3.0 | MIT |
| [react-router-dom](https://github.com/remix-run/react-router) | 7.18.2 | MIT |
| [recharts](https://github.com/recharts/recharts) | 3.10.1 | MIT |
| [redux-persist](https://github.com/rt2zz/redux-persist#readme) | 6.0.0 | MIT |

## Frontend（ビルド・開発ツール）

| ライブラリ | バージョン | ライセンス |
|---|---|---|
| [@eslint/js](https://eslint.org) | 10.0.1 | MIT |
| [@playwright/test](https://playwright.dev) | 1.62.0 | Apache-2.0 |
| [@stryker-mutator/core](https://stryker-mutator.io/) | 9.6.1 | Apache-2.0 |
| [@stryker-mutator/vitest-runner](https://stryker-mutator.io/docs/stryker-js/vitest-runner) | 9.6.1 | Apache-2.0 |
| [@testing-library/jest-dom](https://github.com/testing-library/jest-dom#readme) | 7.0.0 | MIT |
| [@testing-library/react](https://github.com/testing-library/react-testing-library#readme) | 16.3.2 | MIT |
| [@testing-library/user-event](https://github.com/testing-library/user-event#readme) | 14.6.1 | MIT |
| [@types/node](https://github.com/DefinitelyTyped/DefinitelyTyped/tree/master/types/node) | 25.9.5 | MIT |
| [@types/react](https://github.com/DefinitelyTyped/DefinitelyTyped/tree/master/types/react) | 19.2.17 | MIT |
| [@types/react-dom](https://github.com/DefinitelyTyped/DefinitelyTyped/tree/master/types/react-dom) | 19.2.3 | MIT |
| [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/tree/main/packages/plugin-react#readme) | 6.0.4 | MIT |
| [@vitest/coverage-v8](https://vitest.dev/guide/coverage) | 4.1.10 | MIT |
| [concurrently](https://github.com/open-cli-tools/concurrently) | 10.0.4 | MIT |
| [eslint](https://eslint.org) | 10.8.0 | MIT |
| [eslint-config-prettier](https://github.com/prettier/eslint-config-prettier#readme) | 10.1.8 | MIT |
| [eslint-plugin-react-hooks](https://react.dev/) | 7.1.1 | MIT |
| [eslint-plugin-react-refresh](https://github.com/ArnaudBarre/eslint-plugin-react-refresh) | 0.5.3 | MIT |
| [express](https://expressjs.com/) | 5.2.1 | MIT |
| [http-proxy-middleware](https://github.com/chimurai/http-proxy-middleware#readme) | 4.2.0 | MIT |
| [jsdom](https://github.com/jsdom/jsdom) | 29.1.1 | MIT |
| [msw](https://mswjs.io) | 2.15.0 | MIT |
| [openapi-typescript](https://openapi-ts.dev) | 7.13.0 | MIT |
| [playwright](https://playwright.dev) | 1.62.0 | Apache-2.0 |
| [prettier](https://prettier.io) | 3.9.6 | MIT |
| [typescript](https://www.typescriptlang.org/) | 5.9.3 | Apache-2.0 |
| [typescript-eslint](https://typescript-eslint.io/packages/typescript-eslint) | 8.65.0 | MIT |
| [vite](https://vite.dev) | 8.1.5 | MIT |
| [vitest](https://vitest.dev) | 4.1.10 | MIT |
| [wrangler](https://github.com/cloudflare/workers-sdk#readme) | 4.114.0 | MIT OR Apache-2.0 |

## Backend（ランタイム）

| ライブラリ | バージョン | ライセンス |
|---|---|---|
| [alembic](https://alembic.sqlalchemy.org) | 1.18.5 | MIT |
| [anthropic](https://github.com/anthropics/anthropic-sdk-python) | 0.120.2 | MIT License |
| [cryptography](https://github.com/pyca/cryptography) | 50.0.0 | Apache-2.0 OR BSD-3-Clause |
| [fastapi](https://github.com/fastapi/fastapi) | 0.141.1 | MIT |
| [google-cloud-storage](https://github.com/googleapis/google-cloud-python/tree/main/packages/google-cloud-storage) | 3.13.0 | Apache Software License |
| [google-cloud-tasks](https://github.com/googleapis/google-cloud-python/tree/main/packages/google-cloud-tasks) | 2.23.0 | Apache Software License |
| [httpx](https://github.com/encode/httpx) | 0.28.1 | BSD License |
| [markdown](https://Python-Markdown.github.io/) | 3.10.3 | BSD-3-Clause |
| [pyasn1](https://github.com/pyasn1/pyasn1) | 0.6.4 | BSD-2-Clause |
| [pydantic](https://github.com/pydantic/pydantic) | 2.13.4 | MIT |
| [pydyf](https://www.courtbouillon.org/pydyf) | 0.12.1 | BSD License |
| [PyGithub](https://github.com/pygithub/pygithub) | 2.9.1 | GNU Library or Lesser General Public License (LGPL) |
| [PyJWT](https://github.com/jpadilla/pyjwt) | 2.13.0 | MIT |
| [pypdf](https://github.com/py-pdf/pypdf) | 6.14.2 | BSD-3-Clause |
| [python-dotenv](https://github.com/theskumar/python-dotenv) | 1.2.2 | BSD-3-Clause |
| [python-multipart](https://github.com/Kludex/python-multipart) | 0.0.32 | Apache-2.0 |
| [redis](https://github.com/redis/redis-py) | 8.1.0 | MIT |
| [reportlab](https://www.reportlab.com/) | 5.0.0 | BSD License |
| [slowapi](https://github.com/laurents/slowapi) | 0.1.10 | MIT License |
| [sqlalchemy](https://www.sqlalchemy.org) | 2.0.51 | MIT |
| [sqlalchemy-libsql](https://github.com/tursodatabase/libsql-sqlalchemy) | 0.2.0 | MIT License |
| [starlette](https://github.com/Kludex/starlette) | 1.3.1 | BSD-3-Clause |
| [uvicorn](https://uvicorn.dev/) | 0.52.1 | BSD-3-Clause |
| [weasyprint](https://weasyprint.org/) | 69.0 | BSD License |

## Backend（開発ツール）

| ライブラリ | バージョン | ライセンス |
|---|---|---|
| [autopep8](https://github.com/hhatto/autopep8) | 2.3.2 | MIT License |
| [black](https://github.com/psf/black) | 26.5.1 | MIT |
| [isort](https://pycqa.github.io/isort/index.html) | 8.0.1 | MIT |
| [mutmut](https://github.com/boxed/mutmut) | 3.7.0 | BSD-3-Clause |
| [pytest](https://docs.pytest.org/en/latest/) | 9.1.1 | MIT |
| [pytest-cov](https://pypi.org/project/pytest-cov/) | 7.1.0 | MIT |
| [ruff](https://docs.astral.sh/ruff) | 0.16.1 | MIT |

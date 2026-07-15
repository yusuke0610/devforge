{
  description = "DevForge 開発環境";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";

    # backend Python 環境の Nix build 化（ADR-0021 Phase 1）。
    # uv.lock（正本: backend/pyproject.toml + uv.lock / Phase 0）から
    # Python パッケージ一式を Nix derivation として構成する。
    pyproject-nix = {
      url = "github:pyproject-nix/pyproject.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    uv2nix = {
      url = "github:pyproject-nix/uv2nix";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    pyproject-build-systems = {
      url = "github:pyproject-nix/build-system-pkgs";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.uv2nix.follows = "uv2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, flake-utils, pyproject-nix, uv2nix, pyproject-build-systems }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        lib = pkgs.lib;

        # WeasyPrint が必要とするネイティブライブラリ
        weasyPrintLibs = with pkgs; [
          pango
          cairo
          glib
          gobject-introspection
          libffi
          gdk-pixbuf
          fontconfig
          freetype
          harfbuzz
        ];

        # --- backend Python 環境（uv2nix / ADR-0021 Phase 1） ---
        # backend/pyproject.toml + uv.lock を読み、依存を Nix build で構成する。
        # backend は virtual project（[tool.uv] package = false）のため、
        # mkVirtualEnv には依存のみが入る（app/ 本体は PYTHONPATH/cwd で解決）。
        workspace = uv2nix.lib.workspace.loadWorkspace { workspaceRoot = ./backend; };
        # wheel 優先: uv.lock に記録された wheel をそのまま使い、sdist ビルドの
        # ツールチェーン差異（Rust / cmake 等）を持ち込まない
        pyprojectOverlay = workspace.mkPyprojectOverlay { sourcePreference = "wheel"; };
        pythonSet =
          (pkgs.callPackage pyproject-nix.build.packages {
            python = pkgs.python313; # Python 3.13（Dockerfile / requires-python 準拠）
          }).overrideScope (lib.composeManyExtensions [
            pyproject-build-systems.overlays.default
            pyprojectOverlay
          ]);
        # 全依存入りの virtualenv（devshell の python / pytest / ruff / alembic の実体）
        backendEnv = pythonSet.mkVirtualEnv "devforge-backend-env" workspace.deps.default;
      in
      {
        devShells.default = pkgs.mkShell {
          packages = [
            # --- Python (Backend) ---
            # uv2nix で build した全依存入り virtualenv（.venv 廃止 / ADR-0021 Phase 1）。
            # python / pytest / ruff / alembic / uvicorn 等はここから PATH に載る
            backendEnv
          ] ++ (with pkgs; [
            uv                 # uv.lock の更新（uv lock）専用。依存導入には使わない

            # --- Node.js (Frontend) ---
            nodejs_22          # Node.js 22 LTS（npm 同梱）

            # --- WeasyPrint ネイティブ依存 ---
            pango
            cairo
            glib
            gobject-introspection
            libffi
            fontconfig
            freetype
            harfbuzz
            gdk-pixbuf

            # --- ミドルウェア ---
            redis              # Redis 7（ローカル開発用）
            turso-cli          # Turso (libSQL) CLI（ローカル開発用）
            stripe-cli         # Stripe CLI（Webhook 転送 / ローカル決済確認用）

            # --- IaC ---
            opentofu           # OpenTofu CLI（Terraform 互換 / インフラ管理）

            # --- 共通ツール ---
            git
            gh                 # GitHub CLI
            curl
            gnumake
          ]);

          # WeasyPrint が共有ライブラリを発見できるよう動的リンカーのパスを設定
          # macOS の dyld は LD_LIBRARY_PATH を無視するため DYLD_* も設定する
          shellHook = ''
            export LD_LIBRARY_PATH="${pkgs.lib.makeLibraryPath weasyPrintLibs}:$LD_LIBRARY_PATH"
            export DYLD_LIBRARY_PATH="${pkgs.lib.makeLibraryPath weasyPrintLibs}:''${DYLD_LIBRARY_PATH:-}"
            export DYLD_FALLBACK_LIBRARY_PATH="${pkgs.lib.makeLibraryPath weasyPrintLibs}:''${DYLD_FALLBACK_LIBRARY_PATH:-}"

            echo ""
            echo "DevForge 開発環境"
            echo "  Python : $(python3 --version) (nix build: devforge-backend-env)"
            echo "  Node   : $(node --version)"
            echo "  npm    : $(npm --version)"
            echo "  uv     : $(uv --version)"
            echo "  Redis  : $(redis-server --version)"
            echo "  tofu   : $(tofu --version | head -1)"
            echo "  Turso  : $(turso --version 2>/dev/null | head -1)"
            echo "  Stripe : $(stripe version 2>/dev/null | head -1)"
            echo "  gh     : $(gh --version | head -1)"
            echo ""
            echo "セットアップ: make setup"
            echo ""
          '';
        };
      }
    );
}

{
  description = "DevForge 開発環境";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};

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
      in
      {
        devShells.default = pkgs.mkShell {
          packages = with pkgs; [
            # --- Python (Backend) ---
            python313          # Python 3.13（Dockerfile 準拠）
            uv                 # 高速パッケージマネージャ

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
          ];

          # WeasyPrint が共有ライブラリを発見できるよう動的リンカーのパスを設定
          # macOS の dyld は LD_LIBRARY_PATH を無視するため DYLD_* も設定する
          shellHook = ''
            export LD_LIBRARY_PATH="${pkgs.lib.makeLibraryPath weasyPrintLibs}:$LD_LIBRARY_PATH"
            export DYLD_LIBRARY_PATH="${pkgs.lib.makeLibraryPath weasyPrintLibs}:''${DYLD_LIBRARY_PATH:-}"
            export DYLD_FALLBACK_LIBRARY_PATH="${pkgs.lib.makeLibraryPath weasyPrintLibs}:''${DYLD_FALLBACK_LIBRARY_PATH:-}"

            # uv が Python 3.13 を使うよう明示
            export UV_PYTHON="${pkgs.python313}/bin/python3"

            echo ""
            echo "DevForge 開発環境"
            echo "  Python : $(python3 --version)"
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

/**
 * Cloudflare Pages ミドルウェア。
 *
 * /api/* と /auth/* へのリクエストに X-Internal-Secret ヘッダーを付与する。
 * _redirects によって Cloud Run にプロキシされる前にヘッダーを注入することで、
 * Cloud Run への直接アクセスを Cloud Run 側で 403 として弾く多層防御を実現する。
 *
 * INTERNAL_SECRET は Cloudflare Pages ダッシュボードの
 * Settings → Environment Variables で環境ごとに登録すること（dev / prod で別値）。
 */

interface Env {
  INTERNAL_SECRET: string;
}

const PROTECTED_PREFIXES = ["/api/", "/auth/", "/health"];

export const onRequest: PagesFunction<Env> = async (context) => {
  const path = new URL(context.request.url).pathname;
  const needsSecret = PROTECTED_PREFIXES.some((prefix) =>
    path.startsWith(prefix)
  );

  if (!needsSecret) {
    return context.next();
  }

  const secret = context.env.INTERNAL_SECRET;
  const req = new Request(context.request);
  req.headers.set("X-Internal-Secret", secret ?? "");
  return context.next(req);
};

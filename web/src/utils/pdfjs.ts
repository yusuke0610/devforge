/**
 * react-pdf（内部は pdf.js）の worker 設定。
 *
 * このモジュールは PDF を実際に描画する内側ビュー（PdfDocumentView）からのみ import する。
 * PdfDocumentView 自体を React.lazy で遅延ロードするため、react-pdf 本体・pdf.js worker・
 * テキストレイヤー CSS は初期バンドルから切り離され、取り込み機能を使う時だけ読み込まれる。
 *
 * worker URL は Vite の `new URL(..., import.meta.url)` で解決する（react-pdf 公式の Vite 手順）。
 * テキストレイヤーの span 配置は react-pdf 同梱の TextLayer.css に従う。
 */
import { pdfjs } from "react-pdf";
import "react-pdf/dist/Page/TextLayer.css";

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url,
).toString();

export { pdfjs };

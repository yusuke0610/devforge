import { useMemo, useState } from "react";
import styles from "./LanguageBar.module.css";

/**
 * GitHub の言語カラーマッピング。
 * 主要言語のみ定義し、未定義の言語にはフォールバック色を使用。
 */
const LANGUAGE_COLORS: Record<string, string> = {
  Python: "#3572A5",
  TypeScript: "#3178c6",
  JavaScript: "#f1e05a",
  Java: "#b07219",
  Go: "#00ADD8",
  Rust: "#dea584",
  "C++": "#f34b7d",
  C: "#555555",
  "C#": "#178600",
  Ruby: "#701516",
  PHP: "#4F5D95",
  Swift: "#F05138",
  Kotlin: "#A97BFF",
  Dart: "#00B4AB",
  Shell: "#89e051",
  HTML: "#e34c26",
  CSS: "#563d7c",
  SCSS: "#c6538c",
  Vue: "#41b883",
  Svelte: "#ff3e00",
  HCL: "#844FBA",
  Dockerfile: "#384d54",
  Makefile: "#427819",
  Lua: "#000080",
  Scala: "#c22d40",
  Elixir: "#6e4a7e",
  Haskell: "#5e5086",
  R: "#198CE7",
  "Jupyter Notebook": "#DA5B0B",
};

const FALLBACK_COLORS = [
  "#6e7681", "#8b949e", "#7c8088", "#636c76", "#545d68",
];

interface LanguageBarProps {
  languages: Record<string, number>;
}

/**
 * GitHub のリポジトリページ風の言語構成バーを表示するコンポーネント。
 */
export function LanguageBar({ languages }: LanguageBarProps) {
  const [hoveredLang, setHoveredLang] = useState<string | null>(null);

  const items = useMemo(() => {
    const total = Object.values(languages).reduce((sum, v) => sum + v, 0);
    if (total === 0) return [];

    // バイト数降順でソート
    const sorted = Object.entries(languages).sort(([, a], [, b]) => b - a);

    let fallbackIdx = 0;
    return sorted.map(([lang, bytes]) => {
      const percentage = (bytes / total) * 100;
      const color =
        LANGUAGE_COLORS[lang] ??
        FALLBACK_COLORS[fallbackIdx++ % FALLBACK_COLORS.length];
      return { lang, bytes, percentage, color };
    });
  }, [languages]);

  if (items.length === 0) return null;

  // ホバー中のセグメントの中央位置（%）を算出
  const hoveredItem = hoveredLang
    ? items.find((i) => i.lang === hoveredLang)
    : null;
  let tooltipLeft = 0;
  if (hoveredItem) {
    let cumulative = 0;
    for (const item of items) {
      if (item.lang === hoveredLang) {
        tooltipLeft = cumulative + item.percentage / 2;
        break;
      }
      cumulative += item.percentage;
    }
  }

  return (
    <div className={styles.container}>
      {/* カラーバー + ツールチップ */}
      <div className={styles.barWrapper}>
        {hoveredItem && (
          <span
            className={styles.tooltip}
            style={{ left: `${tooltipLeft}%` }}
          >
            {hoveredItem.lang}{" "}
            {hoveredItem.percentage < 0.1
              ? "<0.1"
              : hoveredItem.percentage.toFixed(1)}
            %
          </span>
        )}
        <div className={styles.bar}>
          {items.map(({ lang, percentage, color }) => (
            <span
              key={lang}
              className={`${styles.segment} ${hoveredLang === lang ? styles.segmentHovered : ""}`}
              style={{ width: `${percentage}%`, backgroundColor: color }}
              onMouseEnter={() => setHoveredLang(lang)}
              onMouseLeave={() => setHoveredLang(null)}
            />
          ))}
        </div>
      </div>

      {/* 言語ラベル一覧 */}
      <div className={styles.legend}>
        {items.map(({ lang, percentage, color }) => (
          <span
            key={lang}
            className={`${styles.legendItem} ${hoveredLang === lang ? styles.legendItemHovered : ""}`}
            onMouseEnter={() => setHoveredLang(lang)}
            onMouseLeave={() => setHoveredLang(null)}
          >
            <span
              className={styles.dot}
              style={{ backgroundColor: color }}
            />
            <span className={styles.langName}>{lang}</span>
            <span className={styles.langPercent}>
              {percentage < 0.1 ? "<0.1" : percentage.toFixed(1)}%
            </span>
          </span>
        ))}
      </div>
    </div>
  );
}

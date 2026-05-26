import { useMemo, useState } from "react";
import styles from "./TechBar.module.css";

/** 主要フレームワーク・DevTools・インフラのカラーマッピング */
const TECH_COLORS: Record<string, string> = {
  // フロントエンドフレームワーク
  React: "#61dafb",
  "Next.js": "#0070f3",
  Vue: "#42b883",
  "Nuxt.js": "#00dc82",
  Angular: "#dd0031",
  Svelte: "#ff3e00",
  Astro: "#ff5a03",
  Gatsby: "#663399",
  Remix: "#3992ff",
  // バックエンドフレームワーク
  FastAPI: "#009688",
  Django: "#092e20",
  Flask: "#8a8a8a",
  Express: "#404040",
  NestJS: "#e0234e",
  "Spring Boot": "#6db33f",
  Gin: "#00add8",
  Echo: "#2196f3",
  Fiber: "#00acd7",
  // データ・ML
  Pandas: "#150458",
  NumPy: "#4dabcf",
  "scikit-learn": "#f89939",
  TensorFlow: "#ff6f00",
  PyTorch: "#ee4c2c",
  LangChain: "#1c3c3c",
  // データストア・インフラ系 (dependency 由来)
  SQLAlchemy: "#d71f00",
  GraphQL: "#e10098",
  Redis: "#dc382d",
  MongoDB: "#47a248",
  PostgreSQL: "#336791",
  AWS: "#ff9900",
  GCP: "#4285f4",
  Azure: "#0089d6",
  // DevTools
  Docker: "#2496ed",
  "Docker Compose": "#1d63a1",
  "GitHub Actions": "#2088ff",
  Jenkins: "#d24939",
  "GitLab CI": "#fc6d26",
  CircleCI: "#343434",
  Make: "#427819",
  // インフラ
  Terraform: "#7b42bc",
};

const FALLBACK_COLORS = [
  "#6e7681",
  "#8b949e",
  "#7c8088",
  "#636c76",
  "#545d68",
];

interface TechBarProps {
  /** ツール名 → 使用リポジトリ数 */
  techs: Record<string, number>;
  /** リスト要素の aria-label */
  ariaLabel?: string;
}

export function TechBar({ techs, ariaLabel }: TechBarProps) {
  const [hoveredTech, setHoveredTech] = useState<string | null>(null);

  const items = useMemo(() => {
    const total = Object.values(techs).reduce((sum, v) => sum + v, 0);
    if (total === 0) return [];

    const sorted = Object.entries(techs).sort(([, a], [, b]) => b - a);

    let fallbackIdx = 0;
    return sorted.map(([name, count]) => {
      const percentage = (count / total) * 100;
      const color =
        TECH_COLORS[name] ??
        FALLBACK_COLORS[fallbackIdx++ % FALLBACK_COLORS.length];
      return { name, count, percentage, color };
    });
  }, [techs]);

  if (items.length === 0) return null;

  const hoveredItem = hoveredTech
    ? items.find((i) => i.name === hoveredTech)
    : null;
  let tooltipLeft = 0;
  if (hoveredItem) {
    let cumulative = 0;
    for (const item of items) {
      if (item.name === hoveredTech) {
        tooltipLeft = cumulative + item.percentage / 2;
        break;
      }
      cumulative += item.percentage;
    }
  }

  return (
    <div className={styles.container}>
      <div className={styles.barWrapper}>
        {hoveredItem && (
          <span
            className={styles.tooltip}
            style={{ left: `${tooltipLeft}%` }}
          >
            {hoveredItem.name}{" "}
            {hoveredItem.percentage < 0.1
              ? "<0.1"
              : hoveredItem.percentage.toFixed(1)}
            %
          </span>
        )}
        <div className={styles.bar}>
          {items.map(({ name, percentage, color }) => (
            <span
              key={name}
              className={`${styles.segment} ${hoveredTech === name ? styles.segmentHovered : ""}`}
              style={{ width: `${percentage}%`, backgroundColor: color }}
              onMouseEnter={() => setHoveredTech(name)}
              onMouseLeave={() => setHoveredTech(null)}
            />
          ))}
        </div>
      </div>

      <ul className={styles.legend} aria-label={ariaLabel}>
        {items.map(({ name, percentage, color }) => (
          <li
            key={name}
            className={`${styles.legendItem} ${hoveredTech === name ? styles.legendItemHovered : ""}`}
            onMouseEnter={() => setHoveredTech(name)}
            onMouseLeave={() => setHoveredTech(null)}
          >
            <span className={styles.dot} style={{ backgroundColor: color }} />
            <span className={styles.techName}>{name}</span>
            <span className={styles.techPercent}>
              {percentage < 0.1 ? "<0.1" : percentage.toFixed(1)}%
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

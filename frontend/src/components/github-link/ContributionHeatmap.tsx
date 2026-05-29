import { useMemo } from "react";
import type { ContributionCalendar, ContributionDay } from "../../api";
import styles from "./ContributionHeatmap.module.css";

const MONTH_NAMES = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

const LEVEL_CLASSES = [styles.l0, styles.l1, styles.l2, styles.l3, styles.l4];

interface ContributionHeatmapProps {
  calendar: ContributionCalendar;
}

/**
 * GitHub プロフィールの「緑の四角」を再現するコントリビューションヒートマップ。
 * 列=週・行=曜日でセルを並べ、濃淡レベル (0–4) で色分けする。
 * 年間コントリビュート数と最大連続日数のサマリーも表示する。
 */
export function ContributionHeatmap({ calendar }: ContributionHeatmapProps) {
  // weeks は OpenAPI 生成型では optional（backend の default_factory 由来）。null 合体で安定参照にする。
  const weeks = useMemo(() => calendar.weeks ?? [], [calendar.weeks]);

  /** 各週の先頭日から月ラベルを算出する（前の週から月が変わる週にのみ表示） */
  const monthLabels = useMemo(() => {
    // "YYYY-MM-DD" は UTC 深夜として parse されるため、ローカル TZ で月がずれない
    // よう getUTCMonth() で月を取り出す（負オフセット TZ での月境界ずれを防ぐ）
    const monthOf = (week: ContributionDay[]) =>
      week[0] ? new Date(week[0].date).getUTCMonth() : -1;
    return weeks.map((week, i) => {
      const month = monthOf(week);
      if (month < 0) return "";
      const prevMonth = i > 0 ? monthOf(weeks[i - 1]) : -1;
      return month !== prevMonth ? MONTH_NAMES[month] : "";
    });
  }, [weeks]);

  /** 連続コントリビュート日数の最大値を算出する */
  const longestStreak = useMemo(() => {
    let longest = 0;
    let current = 0;
    for (const day of weeks.flat()) {
      if (day.count > 0) {
        current += 1;
        longest = Math.max(longest, current);
      } else {
        current = 0;
      }
    }
    return longest;
  }, [weeks]);

  return (
    <div className={styles.container}>
      <div className={styles.summary}>
        <div className={styles.statCard}>
          <div className={styles.statValue}>{calendar.total_contributions}</div>
          <div className={styles.statLabel}>年間コントリビュート</div>
        </div>
        <div className={styles.statCard}>
          <div className={styles.statValue}>{longestStreak}</div>
          <div className={styles.statLabel}>最大連続日数</div>
        </div>
      </div>

      <div
        className={styles.scroll}
        role="img"
        aria-label={`過去1年のコントリビューション (合計 ${calendar.total_contributions})`}
      >
        <div className={styles.monthRow}>
          {monthLabels.map((label, i) => (
            <span key={i} className={styles.monthLabel}>
              {label}
            </span>
          ))}
        </div>
        <div className={styles.grid}>
          {weeks.map((week, wi) => (
            <div key={wi} className={styles.weekCol}>
              {week.map((day) => (
                <span
                  key={day.date}
                  className={`${styles.cell} ${LEVEL_CLASSES[day.level] ?? styles.l0}`}
                  title={`${day.date}: ${day.count} contributions`}
                />
              ))}
            </div>
          ))}
        </div>
      </div>

      <div className={styles.legend}>
        <span className={styles.legendText}>Less</span>
        {LEVEL_CLASSES.map((cls, i) => (
          <span key={i} className={`${styles.cell} ${cls}`} />
        ))}
        <span className={styles.legendText}>More</span>
      </div>
    </div>
  );
}

---
paths:
  - web/**
---

# Frontend コンポーネント設計ルール

`web/architecture.md` が「何があるか」を示すのに対し、このファイルは「コンポーネント設計の判断基準」を補完する。
行数はあくまで目安（強制閾値ではない）。超過した場合に責務が複数混在していないかを確認するトリガーとして使う。

## 行数の目安

| 対象 | 目安 | 判断 |
|---|---|---|
| コンポーネント（`.tsx`） | 300 行超 | 分割を検討する |
| コンポーネント（`.tsx`） | 500 行超 | 責務が複数混在している可能性が高い。必ず分割する |
| カスタムフック（`.ts`） | 150 行超 | 分割を検討する |

- ページコンポーネント（`pages/`）は薄いラッパーを保つ。ロジックはカスタムフックへ移動する
- 「行数が少ないから問題ない」ではなく「責務が1つに絞られているか」を本質的な判断基準とする

## props drilling の定義と Context 導入の判断基準

**props drilling の定義**: 中間コンポーネントが実際には使わない props を、下位コンポーネントへ「素通し」で渡す構造。

```tsx
// Bad: ParentForm → ChildSection → GrandchildEditor で同じハンドラ群を素通し
// ChildSection は onUpdateField / onAddItem / focusLocator を自分では使わず下に渡すだけ
<ChildSection
  onUpdateField={onUpdateField}
  onAddItem={onAddItem}
  focusLocator={focusLocator}
/>
// ChildSection の中身
<GrandchildEditor
  onUpdateField={onUpdateField}
  onAddItem={onAddItem}
  focusLocator={focusLocator}
/>
```

**Context 導入の判断基準**:
- 同じ props を **3 層以上素通し**する場合は Context または専用フックによる解消を検討する
- 2 層までの素通しは許容（過剰な Context 導入を避ける）
- 「素通し」か「実際に使っている」かを区別する。中間コンポーネントが props を使っていれば drilling ではない

**Context を導入すべき条件**:
- drilling が 3 層以上 AND 複数の並列コンポーネントが同じ状態・ハンドラを参照する場合

## モーダル管理パターン

親コンポーネントに `useState` でモーダル開閉状態が 3 個以上になったら専用フックに切り出す。

```tsx
// Bad: 親コンポーネントに複数のモーダル状態が並ぶ
const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
const [showSaveConfirm, setShowSaveConfirm] = useState(false);
const [editingField, setEditingField] = useState<"career_summary" | "self_pr" | null>(null);
// さらに PdfPreviewModal の状態も...
```

```tsx
// Good: 専用フックに切り出す（useProjectModalState パターンを参照）
// hooks/career/useProjectModalState.ts の設計に倣う
const { isOpen, openModal, closeModal, modalProject } = useProjectModalState(formState);

// 複数のモーダルを1フックにまとめる（関連度が高い場合）
const { deleteConfirm, saveConfirm, markdownField, openDeleteConfirm, ... } = useCareerFormModals();
```

## 既存の良いパターンへの参照

新規実装時は以下を規範として参照する。

| パターン | ファイル | 用途 |
|---|---|---|
| フォーム CRUD 共通化 | `hooks/useDocumentForm.ts` | loading/saving/error/cache 状態を一元管理 |
| モーダル状態の切り出し | `hooks/career/useProjectModalState.ts` | モーダル開閉・対象オブジェクト管理の規範例 |
| 更新ハンドラ群の切り出し | `hooks/career/useCareerExperienceMutators.ts` | 複数の mutation ハンドラをフックに集約 |
| 非同期タスク進捗 | `hooks/useTaskPolling.ts` | ポーリングロジックをフックに切り出した例 |
| 汎用 UI コンポーネント | `components/ui/` | 新規共通 UI の置き場（toast/, Skeleton 等が既存） |

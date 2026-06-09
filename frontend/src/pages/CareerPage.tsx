import { CareerResumeForm } from "../components/forms/CareerResumeForm";

/**
 * 職務経歴書ページ。
 * `isAuthenticated=false`（未ログインのお試し入力）では保存時にログインを促す。
 */
export default function CareerPage({ isAuthenticated }: { isAuthenticated: boolean }) {
  return <CareerResumeForm isAuthenticated={isAuthenticated} />;
}

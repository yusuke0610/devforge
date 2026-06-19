import { LoginForm } from "../components/auth/LoginForm";

export default function LoginPage({
  githubError,
}: {
  githubError: string | null;
}) {
  return <LoginForm githubError={githubError} />;
}

import { ERROR_CONFIG } from "../constants/errorMessages";
import { generateErrorId } from "./errorId";

export type AppErrorState = {
  code: string;
  message: string;
  action: string | null;
  retryAfter: number | null;
  errorId: string;
};

type ApiErrorInit = {
  code?: string;
  message: string;
  action?: string | null;
  retryAfter?: number | null;
  errorId?: string | null;
};

export class ApiError extends Error {
  code: string;
  action: string | null;
  retryAfter: number | null;
  errorId: string;

  constructor({ code = "INTERNAL_ERROR", message, action = null, retryAfter = null, errorId }: ApiErrorInit) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.action = action;
    this.retryAfter = retryAfter;
    this.errorId = errorId ?? generateErrorId();
  }
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}

export function toAppError(
  error: unknown,
  fallbackMessage = ERROR_CONFIG.INTERNAL_ERROR.message,
): AppErrorState {
  if (isApiError(error)) {
    return {
      code: error.code,
      message: error.message,
      action: error.action,
      retryAfter: error.retryAfter,
      errorId: error.errorId,
    };
  }

  if (error instanceof Error) {
    return {
      code: "INTERNAL_ERROR",
      message: error.message || fallbackMessage,
      action: null,
      retryAfter: null,
      errorId: generateErrorId(),
    };
  }

  return {
    code: "INTERNAL_ERROR",
    message: fallbackMessage,
    action: null,
    retryAfter: null,
    errorId: generateErrorId(),
  };
}

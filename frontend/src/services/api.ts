import axios from "axios";

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";

export const api = axios.create({ baseURL: API_BASE_URL });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("access_token");
      localStorage.removeItem("current_user");
      if (!window.location.pathname.startsWith("/login")) {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

export function apiErrorMessage(error: unknown, fallback = "Something went wrong. Please try again."): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail.length > 0) {
      return detail.map((d: any) => d.msg || d.detail || JSON.stringify(d)).join(", ");
    }
    if (error.response?.data?.message) return String(error.response.data.message);
    if (error.code === "ERR_NETWORK" || !error.response) {
      return "Network error: Unable to reach backend server. Please ensure backend is running.";
    }
    if (error.message) return error.message;
  }
  return fallback;
}

export function resolveAssetUrl(path: string | null | undefined): string {
  if (!path) return "";
  const trimmed = path.trim();
  if (trimmed.startsWith("http://") || trimmed.startsWith("https://") || trimmed.startsWith("blob:") || trimmed.startsWith("data:")) {
    return trimmed;
  }
  const origin = API_BASE_URL.replace(/\/api\/?$/, "");
  // Normalize Windows backslashes (\) to forward slashes (/) and ensure single leading slash
  const normalized = trimmed.replace(/\\/g, "/").replace(/^\.?\/?/, "/");
  return `${origin}${normalized}`;
}

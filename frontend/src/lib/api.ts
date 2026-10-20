import type {
  Profile,
  ChartSpec,
  Chart,
  AIStatus,
  ChatReply,
  Rows,
} from "./schemas";
const base = process.env.NEXT_PUBLIC_API_URL || "";
export class APIError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}
async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${base}/api${path}`, {
    ...options,
    credentials: "include",
    headers: {
      ...(options?.body && typeof options.body === "string"
        ? { "Content-Type": "application/json" }
        : {}),
      ...options?.headers,
    },
  });
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new APIError(
      error?.error?.message ||
        "The server could not complete this request. Please try again.",
      response.status,
    );
  }
  return response.status === 204 ? (undefined as T) : response.json();
}
export const api = {
  health: () =>
    request<{ status: string; max_upload_mb: number; ttl_seconds: number }>(
      "/health",
    ),
  status: () => request<AIStatus>("/ai/status"),
  datasets: () => request<{ datasets: Profile[] }>("/datasets"),
  sample: (name: "plants" | "environment") =>
    request<Profile>("/datasets/sample", {
      method: "POST",
      body: JSON.stringify({ name }),
    }),
  remove: (id: string) =>
    request<void>(`/datasets/${id}`, { method: "DELETE" }),
  recommendations: (id: string, ai = false) =>
    request<{ charts: Chart[]; ai_refined: boolean; note: string }>(
      `/datasets/${id}/recommendations?use_ai=${ai}`,
    ),
  chart: (id: string, spec: ChartSpec) =>
    request<Chart>(`/datasets/${id}/charts`, {
      method: "POST",
      body: JSON.stringify(spec),
    }),
  chat: (id: string, message: string) =>
    request<ChatReply>(`/datasets/${id}/chat`, {
      method: "POST",
      body: JSON.stringify({ message }),
    }),
  rows: (id: string, params: URLSearchParams, signal?: AbortSignal) =>
    request<Rows>(`/datasets/${id}/rows?${params}`, { signal }),
  upload: (file: File, onProgress: (progress: number) => void) =>
    new Promise<Profile>((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", `${base}/api/datasets/upload`);
      xhr.withCredentials = true;
      xhr.timeout = 120000;
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable)
          onProgress(Math.round((e.loaded / e.total) * 90));
      };
      xhr.onload = () => {
        try {
          const data = JSON.parse(xhr.responseText);
          if (xhr.status >= 200 && xhr.status < 300) resolve(data);
          else
            reject(
              new APIError(
                data?.error?.message || "Import failed.",
                xhr.status,
              ),
            );
        } catch {
          reject(
            new Error(
              "Unexpected server response. Check that the backend is running.",
            ),
          );
        }
      };
      xhr.onerror = () =>
        reject(
          new Error(
            "Cannot reach the backend. Check that it is running and try again.",
          ),
        );
      xhr.ontimeout = () =>
        reject(new Error("Import timed out. Try a smaller CSV."));
      const form = new FormData();
      form.append("file", file);
      xhr.send(form);
    }),
};

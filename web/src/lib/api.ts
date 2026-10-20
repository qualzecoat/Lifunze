/** Klien API Lifunze — cookie sesi httpOnly + header CSRF (double-submit). */

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export interface User {
  id: number;
  username: string;
  nama_lengkap: string | null;
  email: string | null;
  role: "admin" | "guru" | "siswa";
  must_change_password: boolean;
}

function csrfFromCookie(): string {
  const m = document.cookie.match(/(?:^|;\s*)lifunze_csrf=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : "";
}

export async function apiFetch<T = unknown>(
  path: string,
  opts: { method?: string; body?: unknown; formData?: FormData } = {},
): Promise<T> {
  const method = opts.method ?? "GET";
  const headers: Record<string, string> = {};
  let body: BodyInit | undefined;
  if (opts.formData) {
    body = opts.formData;
  } else if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.body);
  }
  if (method !== "GET") {
    const csrf = csrfFromCookie();
    if (csrf) headers["x-csrf-token"] = csrf;
  }
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body,
    credentials: "include",
  });
  if (!res.ok) {
    let pesan = `Gagal (${res.status})`;
    try {
      const data = await res.json();
      if (data?.detail) pesan = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
    } catch {
      /* abaikan */
    }
    throw new Error(pesan);
  }
  return (await res.json()) as T;
}

export async function getMe(): Promise<User | null> {
  try {
    return await apiFetch<User>("/api/v1/auth/me");
  } catch {
    return null;
  }
}

export async function logout(): Promise<void> {
  try {
    await apiFetch("/api/v1/auth/logout", { method: "POST" });
  } catch {
    /* sesi mungkin sudah berakhir */
  }
}

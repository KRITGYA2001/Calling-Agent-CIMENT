export const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? ''

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${API_BASE}/api/vapi${path}`, init)
  if (!resp.ok) {
    let detail = resp.statusText
    try {
      const body = await resp.json()
      detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch {
      /* keep statusText */
    }
    throw new Error(detail)
  }
  return resp.json() as Promise<T>
}

import { vi } from 'vitest'

/** A minimal stand-in for a fetch Response carrying a JSON body. */
export function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as unknown as Response
}

/** A failed response whose body is not JSON (e.g. a proxy error page). */
export function brokenResponse(status: number): Response {
  return {
    ok: false,
    status,
    json: async () => {
      throw new SyntaxError('Unexpected token <')
    },
  } as unknown as Response
}

/** Replace the global fetch with a mock and return it. */
export function stubFetch() {
  const fetchMock = vi.fn<typeof fetch>()
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

/** The URL of the n-th fetch call, parsed. */
export function calledUrl(fetchMock: ReturnType<typeof stubFetch>, call = 0): URL {
  return new URL(String(fetchMock.mock.calls[call]?.[0]))
}

/** The request options of the n-th fetch call. */
export function calledInit(fetchMock: ReturnType<typeof stubFetch>, call = 0): RequestInit {
  return fetchMock.mock.calls[call]?.[1] ?? {}
}

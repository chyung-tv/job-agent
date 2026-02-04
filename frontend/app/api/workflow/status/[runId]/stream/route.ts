/**
 * Proxy for workflow run status SSE stream.
 * Browser EventSource cannot send X-API-Key; this route calls the backend
 * with the key and streams the response so the client stays same-origin (no CORS).
 */

export const maxDuration = 600;

function getBackendUrl(): string {
  const url = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  return url.replace(/\/$/, "");
}

function getApiKey(): string | undefined {
  return process.env.API_KEY;
}

function createLoggingStream(
  runId: string,
  body: ReadableStream<Uint8Array>
): ReadableStream<Uint8Array> {
  const decoder = new TextDecoder();
  let buffer = "";
  return body.pipeThrough(
    new TransformStream<Uint8Array, Uint8Array>({
      transform(chunk, controller) {
        buffer += decoder.decode(chunk, { stream: true });
        const events = buffer.split(/\n\n/);
        buffer = events.pop() ?? "";
        for (const event of events) {
          const dataLine = event
            .split("\n")
            .find((line) => line.startsWith("data:"));
          if (dataLine) {
            const json = dataLine.slice(5).trim();
            if (json !== "[DONE]" && json) {
              try {
                const data = JSON.parse(json);
                console.log("[SSE proxy] runId:", runId, "event:", data);
              } catch {
                console.log("[SSE proxy] runId:", runId, "data:", json.slice(0, 80));
              }
            }
          }
        }
        controller.enqueue(chunk);
      },
    })
  );
}

export async function GET(
  request: Request,
  context: { params: Promise<{ runId: string }> }
) {
  const { runId } = await context.params;
  const apiKey = getApiKey();

  console.log("[SSE proxy] runId:", runId, "connecting to backend");

  if (!apiKey) {
    return new Response(
      JSON.stringify({ detail: "API key not configured" }),
      { status: 500, headers: { "Content-Type": "application/json" } }
    );
  }

  const backendUrl = getBackendUrl();
  const streamUrl = `${backendUrl}/workflow/status/${runId}/stream`;

  try {
    const backendResponse = await fetch(streamUrl, {
      method: "GET",
      headers: {
        "X-API-Key": apiKey,
      },
      signal: request.signal,
    });

    if (!backendResponse.ok) {
      const text = await backendResponse.text().catch(() => "");
      return new Response(text || backendResponse.statusText, {
        status: backendResponse.status,
        headers: { "Content-Type": "text/plain" },
      });
    }

    console.log("[SSE proxy] runId:", runId, "stream started");

    const headers = new Headers();
    headers.set("Content-Type", "text/event-stream");
    headers.set("Cache-Control", "no-cache");
    headers.set("Connection", "keep-alive");

    const loggingBody = createLoggingStream(
      runId,
      backendResponse.body!
    );

    return new Response(loggingBody, {
      status: 200,
      headers,
    });
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") {
      return new Response(null, { status: 499 });
    }
    return new Response(
      JSON.stringify({ detail: "Failed to connect to workflow status stream" }),
      { status: 502, headers: { "Content-Type": "application/json" } }
    );
  }
}

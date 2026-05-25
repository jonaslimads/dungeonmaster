export const VOICE_BASE_URL =
  process.env.NEXT_PUBLIC_VOICE_BASE_URL ?? "http://localhost:8000";

export const API_TOKEN =
  process.env.NEXT_PUBLIC_API_TOKEN ?? "dev-token-change-me";

export type SSEEvent =
  | { event: "received"; filename: string; size: number }
  | { event: "transcript"; text: string }
  | { event: "assistant"; text: string }
  | { event: "error"; message: string }
  | { event: "done" };

export async function sendAudio(
  audioBlob: Blob,
  onEvent: (evt: SSEEvent) => void,
): Promise<void> {
  const formData = new FormData();
  formData.append("audio", audioBlob, "recording.webm");

  const response = await fetch(`${VOICE_BASE_URL}/api/turn/audio`, {
    method: "POST",
    headers: { Authorization: `Bearer ${API_TOKEN}` },
    body: formData,
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }

  const reader = response.body?.getReader();
  if (!reader) throw new Error("No response body");

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const json = line.slice(6);
      try {
        const evt = JSON.parse(json) as SSEEvent;
        onEvent(evt);
      } catch {
        // skip malformed
      }
    }
  }
}

export async function sendText(
  message: string,
  onEvent: (evt: SSEEvent) => void,
): Promise<void> {
  const response = await fetch(`${VOICE_BASE_URL}/api/turn/text`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${API_TOKEN}`,
    },
    body: JSON.stringify({ message }),
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }

  const reader = response.body?.getReader();
  if (!reader) throw new Error("No response body");

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const json = line.slice(6);
      try {
        const evt = JSON.parse(json) as SSEEvent;
        onEvent(evt);
      } catch {
        // skip malformed
      }
    }
  }
}

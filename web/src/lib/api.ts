export const VOICE_BASE_URL =
  process.env.NEXT_PUBLIC_VOICE_BASE_URL ?? "http://localhost:8000";

export const API_TOKEN =
  process.env.NEXT_PUBLIC_API_TOKEN ?? "dev-token-change-me";

export const TTS_VOICES = [
  { id: "pf_dora", name: "Dora", gender: "F" },
  { id: "pm_alex", name: "Alex", gender: "M" },
  { id: "pm_santa", name: "Santa", gender: "M" },
] as const;

export type SSEEvent =
  | { event: "received"; filename: string; size: number }
  | { event: "transcript"; text: string }
  | { event: "assistant"; text: string }
  | { event: "audio"; voice: string; audio: string }
  | { event: "error"; message: string }
  | { event: "done" };

export async function sendAudio(
  audioBlob: Blob,
  voice: string,
  onEvent: (evt: SSEEvent) => void,
): Promise<void> {
  const formData = new FormData();
  formData.append("audio", audioBlob, "recording.webm");

  const url = new URL(`${VOICE_BASE_URL}/api/turn/audio`);
  url.searchParams.set("voice", voice);
  console.log("[sendAudio] voice=", voice, "url=", url.toString());

  const response = await fetch(url.toString(), {
    method: "POST",
    headers: {
      Authorization: `Bearer ${API_TOKEN}`,
    },
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

/**
 * Play a base64-encoded MP3 audio blob.
 */
export async function playAudio(base64Audio: string): Promise<void> {
  const binary = atob(base64Audio);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  const blob = new Blob([bytes], { type: "audio/mpeg" });
  const url = URL.createObjectURL(blob);
  const audio = new Audio(url);
  await audio.play();
  audio.addEventListener("ended", () => URL.revokeObjectURL(url));
}

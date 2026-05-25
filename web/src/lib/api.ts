export const VOICE_BASE_URL =
  process.env.NEXT_PUBLIC_VOICE_BASE_URL ?? "http://localhost:8000";

export const API_TOKEN =
  process.env.NEXT_PUBLIC_API_TOKEN ?? "dev-token-change-me";

export type TurnResponse = {
  transcript: string;
  assistant_text: string;
};

export async function sendAudio(audioBlob: Blob): Promise<TurnResponse> {
  const formData = new FormData();
  formData.append("audio", audioBlob, "recording.webm");

  const response = await fetch(`${VOICE_BASE_URL}/api/turn/audio`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${API_TOKEN}`,
    },
    body: formData,
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }

  return response.json() as Promise<TurnResponse>;
}

export async function sendText(message: string): Promise<TurnResponse> {
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

  return response.json() as Promise<TurnResponse>;
}

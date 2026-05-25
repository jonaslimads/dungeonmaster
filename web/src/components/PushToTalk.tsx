"use client";

import { useRef, useState, useCallback } from "react";
import { sendAudio, type TurnResponse } from "@/lib/api";

export function PushToTalk() {
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const [isRecording, setIsRecording] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [assistantText, setAssistantText] = useState("");
  const [error, setError] = useState<string | null>(null);

  const startRecording = useCallback(async () => {
    setError(null);

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setError(
        "Microphone unavailable. Access via https:// or http://localhost. Browsers block media on non-localhost HTTP.",
      );
      return;
    }

    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (err) {
      const msg =
        err instanceof DOMException && err.name === "NotAllowedError"
          ? "Microphone permission denied. Check browser settings."
          : err instanceof DOMException
            ? `Media error: ${err.message}`
            : "Could not access microphone.";
      setError(msg);
      return;
    }

    chunksRef.current = [];

    const mimeType = MediaRecorder.isTypeSupported("audio/webm")
      ? "audio/webm"
      : "audio/ogg";

    const recorder = new MediaRecorder(stream, { mimeType });

    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        chunksRef.current.push(event.data);
      }
    };

    recorder.onstop = async () => {
      stream.getTracks().forEach((track) => track.stop());
      const audioBlob = new Blob(chunksRef.current, { type: mimeType });
      await handleAudio(audioBlob);
    };

    mediaRecorderRef.current = recorder;
    recorder.start();
    setIsRecording(true);
  }, []);

  const stopRecording = useCallback(() => {
    const recorder = mediaRecorderRef.current;
    if (!recorder || recorder.state === "inactive") return;
    recorder.stop();
    setIsRecording(false);
  }, []);

  async function handleAudio(audioBlob: Blob) {
    setIsLoading(true);
    try {
      const data = await sendAudio(audioBlob);
      setTranscript(data.transcript);
      setAssistantText(data.assistant_text);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <main className="flex min-h-screen flex-col bg-gradient-to-b from-gray-950 via-gray-900 to-gray-950 text-white">
      <header className="flex items-center justify-between border-b border-gray-800 px-6 py-4">
        <h1 className="text-xl font-bold tracking-tight">
          <span className="text-amber-400">⚔️</span> dungeonmaster
        </h1>
        <div className="flex items-center gap-2 text-xs text-gray-500">
          <span className="inline-block h-2 w-2 rounded-full bg-emerald-500"></span>
          voice ready
        </div>
      </header>

      <div className="flex flex-1 flex-col items-center justify-center gap-8 px-6">
        <button
          className={`group relative flex h-40 w-40 items-center justify-center rounded-full border-4 transition-all duration-200 active:scale-95 ${
            isRecording
              ? "border-red-500 bg-red-500/20 shadow-[0_0_40px_rgba(239,68,68,0.3)]"
              : isLoading
                ? "border-gray-600 bg-gray-800/50"
                : "border-gray-600 bg-gray-800/50 shadow-lg hover:border-amber-400 hover:shadow-[0_0_30px_rgba(251,191,36,0.15)]"
          }`}
          onPointerDown={startRecording}
          onPointerUp={stopRecording}
          onPointerCancel={stopRecording}
          disabled={isLoading}
        >
          {isRecording ? (
            <div className="flex flex-col items-center gap-1">
              <div className="h-3 w-3 animate-pulse rounded-full bg-red-500"></div>
              <span className="text-xs font-medium text-red-400">recording</span>
            </div>
          ) : isLoading ? (
            <div className="flex flex-col items-center gap-1">
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-gray-400 border-t-gray-200"></div>
              <span className="text-xs font-medium text-gray-400">processing</span>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-1">
              <svg className="h-8 w-8 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 10v2a7 7 0 0 1-14 0v-2" />
                <line x1="12" y1="19" x2="12" y2="23" strokeLinecap="round" strokeWidth={1.5} />
                <line x1="8" y1="23" x2="16" y2="23" strokeLinecap="round" strokeWidth={1.5} />
              </svg>
              <span className="text-xs font-medium text-gray-400">hold to speak</span>
            </div>
          )}
        </button>

        <p className="text-sm text-gray-500">
          {isRecording ? "release to send" : "press and hold the button"}
        </p>
      </div>

      <section className="mx-auto w-full max-w-2xl space-y-4 px-6 pb-8">
        {error && (
          <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
            {error}
          </div>
        )}

        {transcript && (
          <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4">
            <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-gray-500">
              you
            </h2>
            <p className="whitespace-pre-wrap text-sm text-gray-300">{transcript}</p>
          </div>
        )}

        {assistantText && (
          <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-4">
            <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-amber-500/70">
              🐉 assistant
            </h2>
            <p className="whitespace-pre-wrap text-sm text-gray-200">{assistantText}</p>
          </div>
        )}

        {!transcript && !assistantText && (
          <div className="rounded-xl border border-dashed border-gray-800 p-8 text-center">
            <p className="text-sm text-gray-600">
              Your conversation will appear here...
            </p>
          </div>
        )}
      </section>
    </main>
  );
}

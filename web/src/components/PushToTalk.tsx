"use client";

import { useRef, useState, useCallback } from "react";
import { sendAudio } from "@/lib/api";

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
        "Microphone unavailable. Access via https:// or http://localhost.",
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
    <div className="flex min-h-screen flex-col bg-void-950">
      {/* Ambient background */}
      <div className="pointer-events-none fixed inset-0">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_80%_50%_at_50%_-20%,rgba(234,179,8,0.08),transparent)]" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_60%_40%_at_80%_60%,rgba(120,50,20,0.05),transparent)]" />
      </div>

      {/* Header */}
      <header className="relative z-10 flex items-center justify-between border-b border-void-800/50 px-6 py-4 backdrop-blur-sm">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-dungeon-500/20 text-lg">
            ⚔️
          </div>
          <h1 className="text-lg font-semibold tracking-tight text-void-100">
            dungeonmaster
          </h1>
        </div>
        <div className="flex items-center gap-2 rounded-full border border-emerald-500/20 bg-emerald-500/5 px-3 py-1">
          <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" />
          <span className="text-xs font-medium text-emerald-400/80">
            voice ready
          </span>
        </div>
      </header>

      {/* Main area */}
      <div className="relative z-10 flex flex-1 flex-col items-center justify-center gap-6 px-6">
        {/* Decorative rings */}
        <div className="relative">
          {isRecording && (
            <>
              <div className="absolute inset-0 rounded-full border-2 border-red-500/30 animate-pulse-ring" style={{ margin: "-16px" }} />
              <div className="absolute inset-0 rounded-full border border-red-500/20 animate-pulse-ring" style={{ margin: "-32px", animationDelay: "0.5s" }} />
            </>
          )}

          <button
            className={`group relative flex h-36 w-36 items-center justify-center rounded-full border transition-all duration-300 ${
              isRecording
                ? "border-red-500/50 bg-red-500/10 shadow-[0_0_60px_-15px_rgba(239,68,68,0.4)]"
                : isLoading
                  ? "border-void-700 bg-void-800/80"
                  : "border-void-700 bg-void-900/80 shadow-[0_0_40px_-10px_rgba(0,0,0,0.5)] hover:border-dungeon-500/40 hover:bg-void-800/90 hover:shadow-[0_0_50px_-10px_rgba(234,179,8,0.15)]"
            }`}
            onPointerDown={startRecording}
            onPointerUp={stopRecording}
            onPointerCancel={stopRecording}
            disabled={isLoading}
          >
            {isRecording ? (
              <div className="flex flex-col items-center gap-2">
                <div className="flex gap-1">
                  <span className="h-1 w-1 animate-bounce rounded-full bg-red-400" style={{ animationDelay: "0ms" }} />
                  <span className="h-1 w-1 animate-bounce rounded-full bg-red-400" style={{ animationDelay: "150ms" }} />
                  <span className="h-1 w-1 animate-bounce rounded-full bg-red-400" style={{ animationDelay: "300ms" }} />
                </div>
                <span className="text-[10px] font-semibold uppercase tracking-widest text-red-400/70">
                  recording
                </span>
              </div>
            ) : isLoading ? (
              <div className="flex flex-col items-center gap-2">
                <div className="h-5 w-5 animate-spin rounded-full border-[2px] border-void-600 border-t-dungeon-400" />
                <span className="text-[10px] font-semibold uppercase tracking-widest text-void-500">
                  thinking
                </span>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-2 transition-transform duration-200 group-hover:scale-105">
                <svg
                  className="h-8 w-8 text-void-500 transition-colors group-hover:text-dungeon-400"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={1.5}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"
                  />
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M19 10v2a7 7 0 0 1-14 0v-2"
                  />
                  <line
                    x1="12"
                    y1="19"
                    x2="12"
                    y2="23"
                    strokeLinecap="round"
                  />
                  <line
                    x1="8"
                    y1="23"
                    x2="16"
                    y2="23"
                    strokeLinecap="round"
                  />
                </svg>
                <span className="text-[10px] font-semibold uppercase tracking-widest text-void-600 transition-colors group-hover:text-dungeon-400/70">
                  hold
                </span>
              </div>
            )}
          </button>
        </div>

        <p className="text-sm text-void-600">
          {isRecording
            ? "release to send"
            : isLoading
              ? "waiting for response..."
              : "press and hold to speak"}
        </p>
      </div>

      {/* Conversation area */}
      <section className="relative z-10 mx-auto w-full max-w-2xl space-y-3 px-6 pb-10">
        {error && (
          <div className="rounded-xl border border-red-500/20 bg-red-500/5 px-4 py-3 text-sm text-red-400/80 backdrop-blur-sm">
            {error}
          </div>
        )}

        {transcript && (
          <div className="group rounded-xl border border-void-800/50 bg-void-900/50 p-4 backdrop-blur-sm transition-colors hover:border-void-700/50">
            <div className="mb-2 flex items-center gap-2">
              <div className="h-1.5 w-1.5 rounded-full bg-void-500" />
              <span className="text-[10px] font-semibold uppercase tracking-widest text-void-500">
                you
              </span>
            </div>
            <p className="whitespace-pre-wrap text-sm leading-relaxed text-void-300">
              {transcript}
            </p>
          </div>
        )}

        {assistantText && (
          <div className="group rounded-xl border border-dungeon-500/10 bg-dungeon-950/30 p-4 backdrop-blur-sm transition-colors hover:border-dungeon-500/20">
            <div className="mb-2 flex items-center gap-2">
              <span className="text-sm">🐉</span>
              <span className="text-[10px] font-semibold uppercase tracking-widest text-dungeon-500/60">
                dungeonmaster
              </span>
            </div>
            <p className="whitespace-pre-wrap text-sm leading-relaxed text-void-200">
              {assistantText}
            </p>
          </div>
        )}

        {!transcript && !assistantText && !error && (
          <div className="rounded-xl border border-dashed border-void-800/50 p-10 text-center">
            <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-void-800/50 text-lg opacity-50">
              📜
            </div>
            <p className="text-sm text-void-600">
              Your adventure begins here...
            </p>
          </div>
        )}
      </section>
    </div>
  );
}

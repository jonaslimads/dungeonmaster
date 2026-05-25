"use client";

import { useRef, useState, useCallback, useEffect } from "react";
import { sendAudio, type SSEEvent } from "@/lib/api";

type Message =
  | { id: string; type: "system"; text: string }
  | { id: string; type: "user"; text: string }
  | { id: string; type: "assistant"; text: string }
  | { id: string; type: "error"; text: string };

let msgId = 0;
const uid = () => `msg-${++msgId}`;

export function PushToTalk() {
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  const [isRecording, setIsRecording] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);

  const appendMessage = useCallback((msg: Message) => {
    setMessages((prev) => [...prev, msg]);
  }, []);

  // Scroll to bottom on new message
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleEvent = useCallback(
    (evt: SSEEvent) => {
      switch (evt.event) {
        case "received":
          appendMessage({
            id: uid(),
            type: "system",
            text: `audio received (${(evt.size / 1024).toFixed(1)} KB)`,
          });
          break;
        case "transcript":
          appendMessage({ id: uid(), type: "user", text: evt.text });
          break;
        case "assistant":
          appendMessage({ id: uid(), type: "assistant", text: evt.text });
          setIsLoading(false);
          break;
        case "error":
          appendMessage({ id: uid(), type: "error", text: evt.message });
          setIsLoading(false);
          break;
        case "done":
          setIsLoading(false);
          break;
      }
    },
    [appendMessage],
  );

  const startRecording = useCallback(async () => {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      appendMessage({
        id: uid(),
        type: "error",
        text: "Microphone unavailable. Access via https:// or http://localhost.",
      });
      return;
    }

    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (err) {
      const msg =
        err instanceof DOMException && err.name === "NotAllowedError"
          ? "Microphone permission denied."
          : err instanceof DOMException
            ? `Media error: ${err.message}`
            : "Could not access microphone.";
      appendMessage({ id: uid(), type: "error", text: msg });
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
  }, [appendMessage]);

  const stopRecording = useCallback(() => {
    const recorder = mediaRecorderRef.current;
    if (!recorder || recorder.state === "inactive") return;
    recorder.stop();
    setIsRecording(false);
  }, []);

  async function handleAudio(audioBlob: Blob) {
    setIsLoading(true);
    try {
      await sendAudio(audioBlob, handleEvent);
    } catch (err) {
      appendMessage({
        id: uid(),
        type: "error",
        text: err instanceof Error ? err.message : "Unknown error",
      });
      setIsLoading(false);
    }
  }

  return (
    <div className="flex h-[100dvh] flex-col overflow-hidden bg-void-950">
      {/* Ambient background */}
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_80%_50%_at_50%_-20%,rgba(234,179,8,0.08),transparent)]" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_60%_40%_at_80%_60%,rgba(120,50,20,0.05),transparent)]" />
      </div>

      {/* Header */}
      <header className="relative z-10 flex shrink-0 items-center justify-between border-b border-void-800/50 px-5 py-3 backdrop-blur-sm">
        <div className="flex items-center gap-3">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-dungeon-500/20 text-base">
            ⚔️
          </div>
          <h1 className="text-sm font-semibold tracking-tight text-void-100">
            dungeonmaster
          </h1>
        </div>
        <div className="flex items-center gap-2 rounded-full border border-emerald-500/20 bg-emerald-500/5 px-2.5 py-0.5">
          <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" />
          <span className="text-[10px] font-medium text-emerald-400/80">
            voice ready
          </span>
        </div>
      </header>

      {/* Messages - scrollable area */}
      <div
        ref={scrollRef}
        className="relative z-10 flex-1 overflow-y-auto px-5 py-4"
        style={{ minHeight: 0 }}
      >
        <div className="mx-auto max-w-2xl space-y-2">
          {messages.length === 0 && (
            <div className="flex h-full items-center justify-center">
              <div className="rounded-xl border border-dashed border-void-800/50 p-10 text-center">
                <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-void-800/50 text-lg opacity-50">
                  📜
                </div>
                <p className="text-sm text-void-600">
                  Your adventure begins here...
                </p>
              </div>
            </div>
          )}

          {messages.map((msg) => {
            if (msg.type === "system") {
              return (
                <div
                  key={msg.id}
                  className="flex items-center justify-center gap-2 py-1"
                >
                  <span className="h-px w-8 bg-void-800" />
                  <span className="text-[10px] font-medium uppercase tracking-widest text-void-600">
                    {msg.text}
                  </span>
                  <span className="h-px w-8 bg-void-800" />
                </div>
              );
            }

            if (msg.type === "error") {
              return (
                <div
                  key={msg.id}
                  className="rounded-xl border border-red-500/20 bg-red-500/5 px-4 py-3 text-sm text-red-400/80"
                >
                  {msg.text}
                </div>
              );
            }

            if (msg.type === "user") {
              return (
                <div key={msg.id} className="flex justify-end">
                  <div className="max-w-[85%] rounded-2xl rounded-br-sm bg-void-800 px-4 py-2.5">
                    <p className="text-sm leading-relaxed text-void-200">
                      {msg.text}
                    </p>
                  </div>
                </div>
              );
            }

            return (
              <div key={msg.id} className="flex justify-start">
                <div className="max-w-[85%] rounded-2xl rounded-bl-sm border border-dungeon-500/10 bg-dungeon-950/30 px-4 py-2.5">
                  <div className="mb-1 flex items-center gap-1.5">
                    <span className="text-xs">🐉</span>
                    <span className="text-[9px] font-semibold uppercase tracking-widest text-dungeon-500/50">
                      dungeonmaster
                    </span>
                  </div>
                  <p className="text-sm leading-relaxed text-void-200">
                    {msg.text}
                  </p>
                </div>
              </div>
            );
          })}

          {isLoading && (
            <div className="flex justify-start">
              <div className="rounded-2xl rounded-bl-sm border border-void-700/50 bg-void-800/50 px-4 py-3">
                <div className="flex gap-1">
                  <span className="h-2 w-2 animate-bounce rounded-full bg-void-500" style={{ animationDelay: "0ms" }} />
                  <span className="h-2 w-2 animate-bounce rounded-full bg-void-500" style={{ animationDelay: "150ms" }} />
                  <span className="h-2 w-2 animate-bounce rounded-full bg-void-500" style={{ animationDelay: "300ms" }} />
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Bottom button */}
      <div className="relative z-10 flex shrink-0 flex-col items-center gap-3 border-t border-void-800/50 bg-void-950/90 px-5 py-4 backdrop-blur-sm">
        <div className="relative">
          {isRecording && (
            <>
              <div className="absolute inset-0 rounded-full border-2 border-red-500/30" style={{ margin: "-12px", animation: "pulse-ring 2s ease-in-out infinite" }} />
              <div className="absolute inset-0 rounded-full border border-red-500/20" style={{ margin: "-24px", animation: "pulse-ring 2s ease-in-out 0.5s infinite" }} />
            </>
          )}

          <button
            className={`group relative flex h-16 w-16 items-center justify-center rounded-full border transition-all duration-300 ${
              isRecording
                ? "border-red-500/50 bg-red-500/10"
                : isLoading
                  ? "border-void-700 bg-void-800/80"
                  : "border-void-700 bg-void-900/80 hover:border-dungeon-500/40 hover:bg-void-800/90"
            }`}
            onPointerDown={startRecording}
            onPointerUp={stopRecording}
            onPointerCancel={stopRecording}
            disabled={isLoading}
          >
            {isRecording ? (
              <div className="flex gap-1">
                <span className="h-1 w-1 animate-bounce rounded-full bg-red-400" style={{ animationDelay: "0ms" }} />
                <span className="h-1 w-1 animate-bounce rounded-full bg-red-400" style={{ animationDelay: "150ms" }} />
                <span className="h-1 w-1 animate-bounce rounded-full bg-red-400" style={{ animationDelay: "300ms" }} />
              </div>
            ) : isLoading ? (
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-void-600 border-t-dungeon-400" />
            ) : (
              <svg
                className="h-6 w-6 text-void-500 transition-colors group-hover:text-dungeon-400"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={1.5}
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 10v2a7 7 0 0 1-14 0v-2" />
                <line x1="12" y1="19" x2="12" y2="23" strokeLinecap="round" />
                <line x1="8" y1="23" x2="16" y2="23" strokeLinecap="round" />
              </svg>
            )}
          </button>
        </div>

        <p className="text-[10px] font-medium uppercase tracking-widest text-void-600">
          {isRecording
            ? "release to send"
            : isLoading
              ? "processing..."
              : "hold to speak"}
        </p>
      </div>
    </div>
  );
}

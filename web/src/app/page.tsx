"use client";

import { useEffect } from "react";

import { PushToTalk } from "@/components/PushToTalk";
import { VOICE_BASE_URL } from "@/lib/api";

export default function Home() {
  useEffect(() => {
    fetch(`${VOICE_BASE_URL}/api/warmup`, { method: "POST" })
      .then((res) => res.json())
      .then((data) => console.log("[warmup]", data))
      .catch((err) => console.error("[warmup] failed", err));
  }, []);

  return <PushToTalk />;
}

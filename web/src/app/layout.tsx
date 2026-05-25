import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "dungeonmaster",
  description: "Voice-first RPG assistant",
  viewport: "width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="pt-BR" className="dark">
      <body className="flex h-dvh flex-col overflow-hidden antialiased">
        {children}
      </body>
    </html>
  );
}

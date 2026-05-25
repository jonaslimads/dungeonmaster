import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "dungeonmaster",
  description: "Voice-first RPG assistant",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="pt-BR">
      <body className="antialiased">{children}</body>
    </html>
  );
}

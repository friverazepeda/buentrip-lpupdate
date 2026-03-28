import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "LP reports",
  description: "Static LP reporting views",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

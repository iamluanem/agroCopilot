import type { Metadata } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import { AppSidebar, MobileNav } from "@/components/app-sidebar";
import { Providers } from "./providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "AgroCopilot",
  description: "Farm operations copilot — from alert to proof of results.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${GeistSans.variable} ${GeistMono.variable}`}>
      <body>
        <Providers>
          <div className="flex h-dvh flex-col overflow-hidden md:flex-row">
            <AppSidebar />
            <MobileNav />
            <main className="flex min-h-0 min-w-0 flex-1 flex-col pb-14 md:pb-0">{children}</main>
          </div>
        </Providers>
      </body>
    </html>
  );
}

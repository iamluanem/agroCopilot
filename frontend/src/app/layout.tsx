import type { Metadata } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import { AppSidebar } from "@/components/app-sidebar";
import { Providers } from "./providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "AgroCopilot",
  description: "Copiloto operacional da fazenda — do alerta à prova de resultado.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR" className={`${GeistSans.variable} ${GeistMono.variable}`}>
      <body>
        <Providers>
          <div className="flex h-dvh overflow-hidden">
            <AppSidebar />
            <main className="flex min-w-0 flex-1 flex-col">{children}</main>
          </div>
        </Providers>
      </body>
    </html>
  );
}

import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { SiteHeader } from "@/components/layout/SiteHeader";
import "./globals.css";
import { THEME_BOOTSTRAP } from "@/lib/theme/theme-preference";

const geistSans = Geist({
  variable: "--font-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "midwestball",
  description: "Position-aware NFL player stats versus the league.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <head><script dangerouslySetInnerHTML={{ __html: THEME_BOOTSTRAP }} /></head>
      <body className="min-h-full flex flex-col">
        <div className="flex min-h-full flex-1 flex-col bg-background text-foreground">
          <SiteHeader />
          {children}
        </div>
      </body>
    </html>
  );
}

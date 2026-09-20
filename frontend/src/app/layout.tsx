import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "HomeAI — Household Knowledge Base",
  description: "Manage your household items, manuals, and troubleshooting guides.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex" style={{ backgroundColor: '#0a1628' }}>
        {/* Left Sidebar */}
        <nav className="flex flex-col w-56 shrink-0 border-r border-blue-200/20 bg-blue-950/20 p-4">
          <Link href="/" className="mb-6 text-lg font-semibold text-white hover:text-blue-200 transition-colors">
            HomeAI
          </Link>
          <div className="flex flex-col gap-1">
            <Link
              href="/"
              className="rounded-md px-3 py-2 text-sm text-slate-300 hover:bg-blue-100/10 hover:text-white transition-colors"
            >
              🏠 Home
            </Link>
            <Link
              href="/items"
              className="rounded-md px-3 py-2 text-sm text-slate-300 hover:bg-blue-100/10 hover:text-white transition-colors"
            >
              📦 Items
            </Link>
          </div>
        </nav>
        {/* Main content */}
        <div className="flex-1 flex flex-col min-w-0">
          {children}
        </div>
      </body>
    </html>
  );
}

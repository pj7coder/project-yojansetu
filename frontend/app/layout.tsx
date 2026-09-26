import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "YOJANSETU | राष्ट्रीय एवं राज्य जनकल्याण योजना सेतु (भारत)",
  description:
    "All-India AI-Powered Public Welfare Discovery & Statutory Eligibility Verification across Central and State Governments.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="hi" className="h-full">
      <body className="min-h-screen bg-slate-50 text-slate-900 flex flex-col font-sans antialiased selection:bg-orange-500 selection:text-white">
        {children}
      </body>
    </html>
  );
}

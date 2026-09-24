import { Inter } from "next/font/google";
import "./globals.css";
import Link from "next/link";

const inter = Inter({ subsets: ["latin"] });

export const metadata = {
  title: "JobAI Tailoring",
  description: "AI-powered ATS Resume Tailoring",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <nav className="navbar">
          <div className="nav-brand">JobAI</div>
          <div className="nav-links">
            <Link href="/" className="nav-link">Dashboard</Link>
            <Link href="/upload" className="nav-link">New Application</Link>
          </div>
        </nav>
        {children}
      </body>
    </html>
  );
}

import './globals.css';
import type { Metadata, Viewport } from 'next';
import { Fraunces, Inter } from 'next/font/google';

// next/font self-hosts and subsets these at build time — no runtime request to
// Google Fonts, no layout shift. Inter carries the UI; Fraunces (a warm,
// slightly editorial serif) is reserved for the greeting/headline moments so
// the app has a distinct voice instead of reading as default system-ui.
const inter = Inter({ subsets: ['latin'], variable: '--font-ui', display: 'swap' });
const fraunces = Fraunces({
  subsets: ['latin'],
  variable: '--font-display',
  weight: ['500', '600'],
  style: ['normal', 'italic'],
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'me',
  description: 'A daily record of your own thoughts, reflected back to you — nothing else.',
  appleWebApp: {
    capable: true,
    statusBarStyle: 'default',
    title: 'me',
  },
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
  viewportFit: 'cover',
  themeColor: '#f5f6f8',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${fraunces.variable}`}>
      <body>{children}</body>
    </html>
  );
}

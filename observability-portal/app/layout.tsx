import './globals.css';
import type { Metadata, Viewport } from 'next';
import { Plus_Jakarta_Sans } from 'next/font/google';

// next/font self-hosts and subsets this at build time — no runtime request to
// Google Fonts, no layout shift. A single rounded-geometric family (matching
// the approved design reference) carries everything, headline weight for
// greetings/titles and regular weight for body/UI.
const jakarta = Plus_Jakarta_Sans({
  subsets: ['latin'],
  variable: '--font-ui',
  weight: ['400', '500', '600', '700', '800'],
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
  themeColor: '#faf7f2',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={jakarta.variable}>
      <body>{children}</body>
    </html>
  );
}

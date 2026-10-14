import './globals.css';
import type { Metadata, Viewport } from 'next';

export const metadata: Metadata = {
  title: 'selfie.Me',
  description: 'Talk to yourself. Your brain listens, remembers, and only keeps what you say is you.',
  appleWebApp: { capable: true, statusBarStyle: 'black-translucent', title: 'selfie.Me' },
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
  viewportFit: 'cover',
  themeColor: '#0e1915',
};

// Theme is applied before first paint from localStorage so the dark/light
// choice never flashes. Defaults to "dusk".
const themeBoot = `try{var t=localStorage.getItem('selfieme_theme');document.documentElement.dataset.theme=(t==='day'||t==='dusk')?t:'dusk'}catch(e){document.documentElement.dataset.theme='dusk'}`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" data-theme="dusk" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,600;9..40,700&display=swap"
        />
        <script dangerouslySetInnerHTML={{ __html: themeBoot }} />
      </head>
      <body>{children}</body>
    </html>
  );
}

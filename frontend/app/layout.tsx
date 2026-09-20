import './globals.css';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'selfie.Me',
  description: 'Privacy-first personal memory AI starter app',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

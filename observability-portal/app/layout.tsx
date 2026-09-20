import './globals.css';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'me',
  description: 'A daily record of your own thoughts, reflected back to you — nothing else.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

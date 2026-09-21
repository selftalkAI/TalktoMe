import type { MetadataRoute } from 'next';

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: 'me — a daily record of your own thoughts',
    short_name: 'me',
    description: 'A daily record of your own thoughts, reflected back to you — nothing else.',
    start_url: '/',
    display: 'standalone',
    orientation: 'portrait',
    background_color: '#f5f6f8',
    theme_color: '#f5f6f8',
    icons: [
      {
        src: '/icon.svg',
        sizes: 'any',
        type: 'image/svg+xml',
      },
    ],
  };
}

import type { MetadataRoute } from 'next';

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: 'selfie.Me',
    short_name: 'selfie.Me',
    description: 'Talk to yourself. Your brain is listening.',
    start_url: '/',
    display: 'standalone',
    orientation: 'portrait',
    background_color: '#0e1915',
    theme_color: '#0e1915',
    icons: [
      {
        src: '/icon.svg',
        sizes: 'any',
        type: 'image/svg+xml',
      },
    ],
  };
}

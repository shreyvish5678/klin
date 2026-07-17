# Run Work Distill

## Requirements

- Node.js 20 or newer
- npm
- Google Chrome or Chromium for the browser test and demo capture

## Development

```sh
git clone https://github.com/shreyvish5678/work-distill.git
cd work-distill/products/dist-ui
npm ci
npm run dev
```

Open `http://127.0.0.1:5173`.

## Production build

```sh
npm run validate
NODE_ENV=production npm run preview
```

The server remains bound to localhost. To expose it behind a real deployment,
place an authenticated reverse proxy in front of the production process and
retain the evidence and secret-handling boundaries.

## Regenerate media

Keep the local server running, then:

```sh
npm run capture:demo
```

Generated screenshots and the H.264 demo are written to `public/`.

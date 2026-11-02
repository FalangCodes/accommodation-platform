# AccomFind frontend

Next.js 16 / React 19 application for student discovery, landlord management, moderation and administration. It uses TypeScript, Tailwind CSS, TanStack Query, Leaflet and Recharts.

The complete architecture, backend setup, demo data and deployment instructions are in the [project README](../README.md).

## Local development

Use Node.js 22 and npm. From this directory:

```bash
cp .env.example .env.local
npm ci
npm run dev -- --webpack
```

Open <http://localhost:3000>. The backend must be available separately.

## API configuration

```dotenv
NEXT_PUBLIC_API_URL=http://localhost:8000
```

The value is the API origin, without `/api/v1`. Set it explicitly for local development: the current client otherwise falls back to the hosted API. Restart the development server after changing the file.

For Vercel, use `frontend` as the project root and configure `NEXT_PUBLIC_API_URL` with the HTTPS API origin before building. This public variable is included in browser code. Private SMTP, database, Gemini and storage credentials belong only on the backend.

## Checks

```bash
npx tsc --noEmit
npx eslint --max-warnings 0
node --test tests/session.test.mjs
npm run build
```

Run all four checks: a successful TypeScript check alone does not cover lint, session behaviour or production compilation. The session/error tests mock API responses and need no running backend.

## Structure

- `src/app/`: public/authentication pages, profile, landlord dashboard, admin and moderation.
- `src/components/`: shared layout, forms, maps, report views and UI components.
- `src/lib/`: API client, authentication/session state and utilities.
- `public/`: application assets.

Cloud image tiles use Next.js Image with direct, unoptimized URLs to preserve upload delivery and their fixed layout. The full-size lightbox intentionally uses a native image so its natural dimensions preserve the outside-click area.

The retired standalone admin component stubs and unused starter assets have been removed. All role-protected requests remain subject to backend authorization.

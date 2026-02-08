# CLAUDE.md - Coding Preferences

## Development Guidelines
- **Framework**: Next.js (App Router), Tailwind CSS.
- **Style**: Follow Apple Human Interface Guidelines (HIG).
- **Security**: NO .env files or personal config files should EVER be committed. Use 1Password CLI (op) for all secrets. Ensure `.env*` and sensitive files are always in `.gitignore`.
- **Architecture**: Zero-Knowledge (ZK) patterns for privacy-sensitive identity vectors.

## Language
- Primary UI/UX target is Japanese (JP).
- Internal documentation and technical discussions between agents are in English (EN).

## Commands
- **Build**: `npm run build`
- **Dev**: `npm run dev`
- **Lint**: `npm run lint`

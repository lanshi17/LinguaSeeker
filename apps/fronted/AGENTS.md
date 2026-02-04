# Multi-ACMG Frontend

## Project Overview

This is a React-based frontend application for Multi-ACMG (presumably a variant interpretation or bioinformatics tool). It is built with modern frontend tooling and follows standard React conventions.

**Project Name**: muliti-acmg-fronted  
**Version**: 0.0.0  
**License**: Private

## Technology Stack

| Category | Technology | Version |
|----------|------------|---------|
| Framework | React | ^19.2.0 |
| Language | TypeScript | ~5.9.3 |
| Build Tool | Vite (rolldown-vite) | 7.2.5 |
| Package Manager | npm | - |
| Linting | ESLint | ^9.39.1 |

### Key Dependencies
- **react** & **react-dom**: React 19 with StrictMode enabled
- **typescript-eslint**: TypeScript ESLint integration
- **@vitejs/plugin-react**: Official Vite React plugin

### Build Tool Note
This project uses `rolldown-vite` instead of standard Vite for faster build performance. Rolldown is a Rust-based bundler compatible with Rollup's plugin API.

## Project Structure

```
/
├── index.html           # HTML entry point
├── package.json         # Project configuration & dependencies
├── vite.config.ts       # Vite build configuration
├── tsconfig.json        # TypeScript project references
├── tsconfig.app.json    # TypeScript config for application code
├── tsconfig.node.json   # TypeScript config for Node/Vite tooling
├── eslint.config.js     # ESLint configuration
├── public/              # Static assets (served at root)
│   └── vite.svg
└── src/                 # Source code
    ├── main.tsx         # Application entry point
    ├── App.tsx          # Root React component
    ├── App.css          # Component-specific styles
    ├── index.css        # Global styles
    └── assets/          # Asset imports
        └── react.svg
```

## Build Commands

All commands are run via npm:

```bash
# Start development server
npm run dev

# Build for production
npm run build

# Preview production build locally
npm run preview

# Run ESLint
npm run lint
```

### Build Process
The production build runs:
1. `tsc -b` - TypeScript compilation with build mode (project references)
2. `vite build` - Bundle with Vite

Output is generated in the `dist/` directory (gitignored).

## TypeScript Configuration

The project uses TypeScript project references for optimal build performance:

- **`tsconfig.json`**: Root configuration that references child configs
- **`tsconfig.app.json`**: Application code settings
  - Target: ES2022
  - Module: ESNext with bundler resolution
  - JSX: react-jsx transform
  - Strict mode enabled with additional linting rules
  - Includes: `src/**/*`
- **`tsconfig.node.json`**: Tooling configuration for Vite config
  - Target: ES2023
  - Includes: `vite.config.ts`

### TypeScript Strict Settings
- `strict: true`
- `noUnusedLocals: true`
- `noUnusedParameters: true`
- `noFallthroughCasesInSwitch: true`
- `noUncheckedSideEffectImports: true`

## Code Style Guidelines

### ESLint Configuration
Linting is configured in `eslint.config.js` with:
- `@eslint/js` recommended rules
- `typescript-eslint` recommended rules
- `eslint-plugin-react-hooks` recommended rules
- `eslint-plugin-react-refresh` Vite-specific rules
- `globals.browser` for browser globals

### Style Conventions
- Use TypeScript for all code files
- Follow strict TypeScript settings
- Use ESNext module syntax (`import`/`export`)
- Co-locate component styles (e.g., `App.tsx` + `App.css`)
- Global styles in `index.css`

### CSS
- Uses standard CSS (no preprocessor configured)
- Supports light/dark mode via `prefers-color-scheme` media query
- CSS files are imported directly in components

## Development Workflow

### Adding New Components
1. Create component file in `src/`
2. Create associated `.css` file if needed
3. Import and use in parent component or `App.tsx`

### Asset Handling
- Place static assets in `public/` for direct URL access
- Place imported assets in `src/assets/` for processed imports
- Import assets with standard ES module syntax: `import logo from './assets/logo.svg'`

## Testing

No testing framework is currently configured. Consider adding:
- **Vitest** for unit testing (integrates well with Vite)
- **React Testing Library** for component testing
- **Playwright** or **Cypress** for E2E testing

## Deployment

The application is built as a static site:

1. Run `npm run build` to generate `dist/` directory
2. Serve `dist/` with any static file server
3. Ensure all routes fallback to `index.html` for SPA routing

## Security Considerations

- Application runs entirely client-side
- No sensitive configuration in source code
- Standard React XSS protections apply
- External links use `target="_blank"` with proper `rel` attributes

## Notes for AI Agents

- This is a fresh Vite + React + TypeScript template project
- The codebase is minimal - currently just the default Vite starter template
- Follow existing file organization patterns when adding features
- Maintain TypeScript strict mode compliance
- The project uses React 19 (latest version as of setup)

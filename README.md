# Multilingual Document Evidence Collection Platform

🧬 A platform designed to assist researchers in automating gene variant classification based on ACMG/AMP guidelines.

## Features

- **Multilingual PDF Parsing**: Supports documents in Chinese (中文), Japanese (日本語), German (Deutsch), French (Français), and English
- **LLM-Powered Evidence Extraction**: Uses large language models to analyze documents and extract variant evidence
- **ClinVar Integration**: Automatically validates extracted variants against the ClinVar database
- **ACMG/AMP Classification**: Applies ACMG/AMP criteria (PVS1, PS1-4, PM1-6, PP1-5, BA1, BS1-4, BP1-7) to classify variants
- **Interactive HTML Interface**: Modern Vue.js frontend for uploading documents and viewing analysis results

## Technology Stack

- **Frontend**: Vue 3 + TypeScript + Vite
- **Backend**: Rust + Axum
- **Database**: PostgreSQL
- **Cache**: Redis
- **LLM Integration**: Compatible with Ollama and other LLM APIs

## Project Structure

```
├── backend/                 # Rust Axum backend
│   ├── src/
│   │   ├── api/            # API routes and handlers
│   │   ├── clinvar/        # ClinVar API integration
│   │   ├── config/         # Configuration management
│   │   ├── db/             # Database operations
│   │   ├── llm/            # LLM integration for evidence extraction
│   │   ├── models/         # Data models
│   │   ├── services/       # Business logic
│   │   ├── static/         # Static HTML fallback
│   │   ├── error.rs        # Error handling
│   │   └── main.rs         # Application entry point
│   └── Cargo.toml
├── frontend/               # Vue.js frontend
│   ├── src/
│   │   ├── api/           # API client
│   │   ├── components/    # Vue components
│   │   ├── types/         # TypeScript types
│   │   ├── App.vue        # Main application
│   │   └── main.ts        # Entry point
│   ├── package.json
│   └── vite.config.ts
└── README.md
```

## Getting Started

### Prerequisites

- Rust 1.70+
- Node.js 18+
- PostgreSQL 14+
- Redis 7+
- (Optional) Ollama or other LLM service

### Backend Setup

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Create a `.env` file with your configuration:
   ```env
   DATABASE_URL=postgres://user:password@localhost:5432/evidence_platform
   REDIS_URL=redis://localhost:6379
   LLM_API_URL=http://localhost:11434/api/generate
   LLM_API_KEY=your_api_key
   CLINVAR_API_KEY=your_ncbi_api_key  # Optional, for higher rate limits
   HOST=0.0.0.0
   PORT=8080
   ```

3. Build and run the backend:
   ```bash
   cargo build --release
   cargo run --release
   ```

### Frontend Setup

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Start the development server:
   ```bash
   npm run dev
   ```

4. Or build for production:
   ```bash
   npm run build
   ```

### Development

Run both frontend and backend in development mode:

```bash
# Terminal 1 - Backend
cd backend && cargo run

# Terminal 2 - Frontend
cd frontend && npm run dev
```

The frontend development server will proxy API requests to the backend.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/documents` | List all documents |
| POST | `/api/documents` | Upload a document |
| GET | `/api/documents/{id}` | Get document details |
| POST | `/api/documents/{id}/analyze` | Analyze document with LLM |
| GET | `/api/documents/{id}/results` | Get analysis results |

## ACMG/AMP Classification Criteria

The platform supports the following ACMG/AMP evidence criteria:

### Pathogenic Criteria
- **PVS1**: Null variant in gene where LOF is a known mechanism
- **PS1-PS4**: Strong evidence of pathogenicity
- **PM1-PM6**: Moderate evidence of pathogenicity
- **PP1-PP5**: Supporting evidence of pathogenicity

### Benign Criteria
- **BA1**: Allele frequency >5% in population databases
- **BS1-BS4**: Strong evidence of benign impact
- **BP1-BP7**: Supporting evidence of benign impact

## Contributing

Contributions are welcome! Please read our contributing guidelines and submit pull requests.

## License

This project is licensed under the GPL-3.0 License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- ACMG/AMP variant classification guidelines
- ClinVar database from NCBI
- The Rust and Vue.js communities

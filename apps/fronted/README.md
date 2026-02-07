# Multi-ACGM-fronted

A React-based frontend application for the Multi-ACGM project that enables processing and analysis of PDF documents using advanced AI techniques.

## Features

- PDF Upload and Processing
- Advanced Document Analysis
- Interactive Visualization
- Real-time Status Monitoring

## Architecture

This application follows a modern React + TypeScript + Vite architecture with the following key components:

- **Frontend Framework**: React 18 with TypeScript
- **Build Tool**: Vite for fast development
- **Styling**: Tailwind CSS
- **State Management**: Zustand
- **Routing**: React Router DOM
- **HTTP Client**: Axios

## PDF Upload Functionality

### Upload Endpoint

The application supports PDF uploads via a single unified endpoint:

```
POST /api/v1/pdf/upload
```

### Upload Method

- **Form Data Upload**: The application exclusively uses `multipart/form-data` format for PDF uploads
- **File Parameter**: The PDF file should be sent as the `file` parameter
- **Content Type**: `application/pdf` files are accepted

### Example Request

```javascript
const formData = new FormData();
formData.append('file', pdfFile);

const response = await axios.post('/api/v1/pdf/upload', formData, {
  headers: {
    'Content-Type': 'multipart/form-data'
  }
});
```

## Project Structure

```
src/
├── components/          # Reusable UI components
├── pages/              # Page components
├── services/           # API services
├── utils/              # Utility functions
├── store/              # State management (Zustand)
├── hooks/              # Custom React hooks
├── types/              # TypeScript type definitions
└── assets/             # Static assets
```

## Environment Variables

The application uses the following environment variables:

- `VITE_API_BASE_URL` - Base URL for the backend API
- `VITE_APP_TITLE` - Application title

## Development Setup

1. Install dependencies:
```bash
npm install
```

2. Copy environment variables:
```bash
cp .env.local.example .env.local
```

3. Start the development server:
```bash
npm run dev
```

## Building for Production

To build the application for production:

```bash
npm run build
```

## API Documentation

For detailed API documentation, refer to the `api_docs/` directory.

## Technologies Used

- [React](https://reactjs.org/)
- [TypeScript](https://www.typescriptlang.org/)
- [Vite](https://vitejs.dev/)
- [Tailwind CSS](https://tailwindcss.com/)
- [Axios](https://axios-http.com/)
- [Zustand](https://zustand-demo.pmnd.rs/)
- [React Router DOM](https://reactrouter.com/)
- [Lucide React](https://lucide.dev/)

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License.

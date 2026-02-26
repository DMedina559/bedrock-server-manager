# Bedrock Server Manager - V2 Frontend

This is the new React-based frontend for Bedrock Server Manager.

## Development Setup

1.  **Install dependencies**:

    ```bash
    cd frontend/v2
    npm install
    ```

2.  **Start the Backend**:
    Make sure the Python backend is running on port 11325.

    ```bash
    # From project root
    python -m bedrock_server_manager web start --host 0.0.0.0 --port 11325
    ```

3.  **Start the Frontend Dev Server**:
    ```bash
    cd frontend/v2
    npm run dev
    ```
    The dev server will proxy API requests to `http://localhost:11325`.

## Scripts

- `npm run dev`: Start development server.
- `npm run build`: Build for production.
- `npm run lint`: Run ESLint.
- `npm run lint:fix`: Fix linting issues.
- `npm run format`: Format code with Prettier.
- `npm test`: Run tests in watch mode.
- `npm run test:run`: Run tests once.

## Testing

This project uses Vitest for unit testing and React Testing Library.
Run tests with `npm test`.

## Linting & Formatting

We use ESLint and Prettier. Please run `npm run lint:fix` and `npm run format` before committing.

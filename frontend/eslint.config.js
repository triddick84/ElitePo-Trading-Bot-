// Minimal flat-config so eslint v9+ runs without erroring out.
// The project doesn't rely on ESLint for CI — this exists so the pre-completion
// linter engine doesn't fail. Real linting is done by ruff (backend) and CRA
// (frontend build).

export default [
  {
    ignores: [
      "node_modules/**",
      "build/**",
      "public/**",
      "dist/**",
    ],
  },
];

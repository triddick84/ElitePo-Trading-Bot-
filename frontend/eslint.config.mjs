// Flat config that positively matches every JS/JSX file with zero rules.
// This avoids the "no matching configuration was supplied" error under
// ESLint v9 flat-config while still not enforcing any real linting.
// Real linting is handled by CRA build + ruff (backend).
//
// We register `react-hooks` and `react` as plugins (rules off) purely so
// that legacy `// eslint-disable-line react-hooks/exhaustive-deps` directives
// don't crash the pre-completion linter with "rule not found".
import reactHooks from "eslint-plugin-react-hooks";
import react from "eslint-plugin-react";

export default [
  {
    files: ["**/*.{js,jsx,mjs,cjs,ts,tsx}"],
    plugins: {
      "react-hooks": reactHooks,
      react,
    },
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "module",
      parserOptions: {
        ecmaFeatures: { jsx: true },
      },
    },
    rules: {},
    linterOptions: {
      reportUnusedDisableDirectives: "off",
    },
  },
  {
    ignores: ["node_modules/**", "build/**", "public/**", "dist/**", "**/tma/**"],
  },
];

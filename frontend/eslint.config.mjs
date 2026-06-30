import js from "@eslint/js";
import tseslint from "typescript-eslint";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import noHardcodedColors from "./eslint-rules/no-hardcoded-colors.mjs";
const eslintConfig = [
  { ignores: ["dist", ".test-build"] },
  ...tseslint.config(
    js.configs.recommended,
    ...tseslint.configs.recommended,
    {
      files: ["**/*.{ts,tsx}"],
      languageOptions: {
        ecmaVersion: 2020,
      },
      plugins: {
        "react-hooks": reactHooks,
        "react-refresh": reactRefresh,
        "design-tokens": {
          rules: {
            "no-hardcoded-colors": noHardcodedColors,
          },
        },
      },
      rules: {
        ...reactHooks.configs.recommended.rules,
        "react-refresh/only-export-components": [
          "warn",
          { allowConstantExport: true },
        ],
        "design-tokens/no-hardcoded-colors": "warn",
      },
    },
  ),
];

export default eslintConfig;

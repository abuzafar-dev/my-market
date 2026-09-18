import js from '@eslint/js'
import pluginVue from 'eslint-plugin-vue'
import vueEslintConfigPrettier from '@vue/eslint-config-prettier'
import globals from 'globals'

export default [
  {
    ignores: ['dist/**', 'dev-dist/**', 'node_modules/**'],
  },
  js.configs.recommended,
  ...pluginVue.configs['flat/recommended'],
  {
    languageOptions: {
      globals: {
        ...globals.browser,
      },
    },
    rules: {
      // Icon.vue is a deliberate single-word wrapper used everywhere as
      // <Icon />; the multi-word convention exists to avoid clashing with
      // native HTML elements, which a name like "Icon" can't do anyway.
      'vue/multi-word-component-names': ['error', { ignores: ['Icon'] }],
      // Route props (id, etc. via `props: true`) are always supplied by
      // the router — a required default here is noise, not a real gap.
      'vue/require-default-prop': 'off',
    },
  },
  vueEslintConfigPrettier,
]

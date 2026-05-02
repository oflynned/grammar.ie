// @ts-check
import {defineConfig} from 'astro/config';
import {fileURLToPath} from 'node:url';
import tailwindcss from "@tailwindcss/vite";

import mdx from "@astrojs/mdx";

export default defineConfig({
    vite: {
        plugins: [tailwindcss()],
        resolve: {
            alias: {
                '@components': fileURLToPath(new URL('./src/components', import.meta.url)),
            },
        },
    },
    output: 'static',
    integrations: [mdx()],
    markdown: {
        syntaxHighlight: false
    }
});

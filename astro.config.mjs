// @ts-check
import {defineConfig} from 'astro/config';
import {fileURLToPath} from 'node:url';
import tailwindcss from "@tailwindcss/vite";

import mdx from "@astrojs/mdx";
import sitemap from "@astrojs/sitemap";

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
    site: 'https://grammar.ie',
    integrations: [mdx(), sitemap()],
    markdown: {
        syntaxHighlight: false
    }
});

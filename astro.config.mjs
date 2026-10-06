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
    trailingSlash: 'ignore',
    site: 'https://grammar.ie',
    integrations: [
        mdx(),
        sitemap({
            filter: (page) => !page.includes('/404'),
            serialize(item) {
                const url = item.url;
                if (url === 'https://grammar.ie/') {
                    item.changefreq = 'weekly';
                    item.priority = 1.0;
                } else {
                    const segments = new URL(url).pathname.split('/').filter(Boolean);
                    if (segments.length <= 1) {
                        item.changefreq = 'monthly';
                        item.priority = 0.8;
                    } else {
                        item.changefreq = 'monthly';
                        item.priority = 0.7;
                    }
                }
                return item;
            },
        }),
    ],
    markdown: {
        syntaxHighlight: false
    }
});

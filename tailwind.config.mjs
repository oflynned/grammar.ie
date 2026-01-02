/** @type {import('tailwindcss').Config} */

export default {
    content: ['./src/**/*.{astro,html,js,jsx,md,mdx,svelte,ts,tsx,vue}'], theme: {
        extend: {
            typography: ({theme}) => ({
                // We are creating a custom "grammar" theme
                grammar: {
                    css: {
                        '--tw-prose-body': theme('colors.slate[700]'),
                        '--tw-prose-headings': theme('colors.slate[900]'),
                        '--tw-prose-links': theme('colors.emerald[600]'),
                        '--tw-prose-bullets': theme('colors.emerald[500]'),

                        // Adjusting general text size
                        fontSize: '1rem',
                        lineHeight: '1.6',

                        // Customizing Headings (Making them smaller/technical)
                        h2: {
                            fontSize: '1.5rem',
                            fontWeight: '700',
                            marginTop: '2rem',
                            marginBottom: '1rem',
                            letterSpacing: '-0.025em',
                        },
                        h3: {
                            fontSize: '1.25rem', fontWeight: '600', marginTop: '1.5rem', marginBottom: '0.75rem',
                        },

                        // Making Irish examples stand out
                        'ul li': {
                            paddingLeft: '0.5rem',
                        },
                        'li strong': {
                            color: theme('colors.slate[900]'), fontWeight: '700',
                        }, // Style for "translation" text in italics
                        'li em': {
                            color: theme('colors.slate[500]'), fontStyle: 'italic', marginLeft: '0.25rem',
                        },

                        // Code blocks (for grammar formulas)
                        code: {
                            backgroundColor: theme('colors.slate[100]'),
                            padding: '0.2rem 0.4rem',
                            borderRadius: '0.25rem',
                            fontWeight: '500',
                            fontFamily: 'monospace',
                        },
                        'code::before': {content: '""'},
                        'code::after': {content: '""'},
                    },
                },
            }),
        },
    }, plugins: [],
};
// src/content/config.ts
import {defineCollection, z} from 'astro:content';

const content = defineCollection({
    type: 'content',
    schema: z.object({
        title: z.string(),
        category: z.string(),
        description: z.string().optional(),
        tags: z.array(z.string()),
    }),
});

const orderedContent = defineCollection({
    type: 'content',
    schema: z.object({
        index: z.number(),
        title: z.string(),
        category: z.string(),
        description: z.string().optional(),
        tags: z.array(z.string()),
    }),
})

export const collections = {
    'prepositions': content,
    'verbs': content,
    'copula': orderedContent,
};
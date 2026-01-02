// src/content/config.ts
import { defineCollection, z } from 'astro:content';

const prepositions = defineCollection({
    type: 'content',
    schema: z.object({
        title: z.string(),
        category: z.string(),
        description: z.string().optional(),
        tags: z.array(z.string()),
    }),
});

export const collections = {
    'prepositions': prepositions,
};
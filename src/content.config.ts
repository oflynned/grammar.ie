// src/content/config.ts
import { defineCollection, z } from 'astro:content';

const prepositions = defineCollection({
    type: 'content',
    schema: z.object({
        title: z.string(),
        category: z.string(),
        description: z.string().optional(),
        level: z.string().optional(),
    }),
});

export const collections = {
    'prepositions': prepositions,
};
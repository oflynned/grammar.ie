// src/content/config.ts
import {defineCollection, z} from 'astro:content';

const content = defineCollection({
    type: 'content',
    schema: z.object({
        enTitle: z.string(),
        gaTitle: z.string(),
        description: z.string(),
        order: z.number().optional(),
        tags: z.array(z.string()).default([]),
    }).passthrough(),
});

export const collections = {
    'grammar': content,
};

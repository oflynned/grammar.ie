// src/content/config.ts
import {defineCollection, z} from 'astro:content';

const content = defineCollection({
    type: 'content',
    schema: z.object({
        title: z.string().optional(),
        slug: z.string().optional(),
        navTitle: z.string().optional(),
        category: z.string().optional(),
        section: z.string().optional(),
        sectionSlug: z.string().optional(),
        topic: z.string().optional(),
        topicSlug: z.string().optional(),
        description: z.string().optional(),
        difficulty: z.enum(['beginner', 'intermediate', 'advanced', 'reference']).optional(),
        order: z.number().optional(),
        prerequisiteTopics: z.array(z.string()).default([]),
        relatedTopics: z.array(z.string()).default([]),
        canonicalExamples: z.array(z.string()).default([]),
        expectedLayout: z.string().optional(),
        pagePurpose: z.string().optional(),
        tags: z.array(z.string()).default([]),
    }).passthrough(),
});

export const collections = {
    'grammar': content,
};

import type {CollectionEntry} from 'astro:content';

export type GrammarEntry = CollectionEntry<'grammar'>;

export interface BreadcrumbItem {
    title: string;
    url: string;
}

export const defaultSeo = {
    homeTitle: 'Grammar.ie — Modern Irish Grammar Guide & Reference (Gramadach na Gaeilge)',
    description: 'A structured, modern reference guide to Irish grammar (Gramadach na Gaeilge). Master nouns, verbs, initial mutations, prepositions, copula, and syntax with clear rules and examples.',
    keywords: [
        'Irish grammar',
        'Gramadach na Gaeilge',
        'learn Irish',
        'Irish language',
        'Irish verbs',
        'Irish nouns',
        'Irish mutations',
        'Irish prepositions',
        'Gaeilge',
        'Irish grammar guide',
        'Irish syntax',
    ],
    ogImage: 'https://grammar.ie/og-image.png',
    ogImageAlt: 'Grammar.ie — Modern Irish Grammar Guide (Gramadach na Gaeilge)',
    siteUrl: 'https://grammar.ie',
};

export const folderSeoData: Record<string, { seoTitle: string; description: string; gaName: string }> = {
    adjectives: {
        seoTitle: 'Adjectives (An Aidiacht) – Rules, Declensions & Comparison | Grammar.ie',
        description: 'Comprehensive guide to Irish adjectives (An Aidiacht): learn adjective declensions, noun agreement, comparative forms, and adjective prefixes.',
        gaName: 'An Aidiacht',
    },
    adverbs: {
        seoTitle: 'Adverbs (An Dobhriathar) – Formation & Usage | Grammar.ie',
        description: 'Learn how Irish adverbs (An Dobhriathar) are formed and used: adverbial particles (go), directional adverbs, time expressions, and common phrases.',
        gaName: 'An Dobhriathar',
    },
    articles: {
        seoTitle: 'Definite Article (An tAlt Cinnte) & Mutations | Grammar.ie',
        description: 'Complete guide to the Irish definite article (an, na). Understand singular and plural usage and the initial mutations triggered on nouns.',
        gaName: 'An tAlt Cinnte',
    },
    copula: {
        seoTitle: 'The Copula (An Chopail - Is) – Syntax & Classification | Grammar.ie',
        description: 'Master the Irish copula (is): learn classification sentences, identification sentences, syntax rules, and the key differences between is and bí.',
        gaName: 'An Chopail',
    },
    mutations: {
        seoTitle: 'Initial Mutations (Na hAthruithe Tosaigh) – Lenition & Eclipsis | Grammar.ie',
        description: 'Comprehensive guide to Irish initial mutations (Na hAthruithe Tosaigh): lenition (séimhiú), eclipsis (urú), and prefix mutations (t-, h-, n-) with clear rules.',
        gaName: 'Na hAthruithe Tosaigh',
    },
    nouns: {
        seoTitle: 'Nouns (An tAinmfhocal) – Cases, Gender & Declensions | Grammar.ie',
        description: 'Complete reference for Irish nouns (An tAinmfhocal): master masculine and feminine gender, nominative, vocative, and genitive cases, and plural formation.',
        gaName: 'An tAinmfhocal',
    },
    'nouns/declensions': {
        seoTitle: 'Noun Declensions (Díochlaontaí Ainmfhocal) – All 5 Declensions | Grammar.ie',
        description: 'Explore the five declensions of Irish nouns: detailed rules, stem endings, genitive singular inflections, and irregular noun patterns.',
        gaName: 'Díochlaontaí Ainmfhocal',
    },
    numbers: {
        seoTitle: 'Numbers (Na hUimreacha) – Cardinal, Ordinal & Personal | Grammar.ie',
        description: 'Master the Irish numbering system: cardinal numbers, ordinal numbers, personal numbers (áireamh daoine), fractions, and counting rules.',
        gaName: 'Na hUimreacha',
    },
    other: {
        seoTitle: 'Grammar Resources & Recommended Books | Grammar.ie',
        description: 'Discover recommended Irish grammar books, reference materials, compass directions, and background notes for language learners.',
        gaName: 'Acmhainní Eile',
    },
    prepositions: {
        seoTitle: 'Prepositions (Réamhfhocail) – Simple, Compound & Conjugated | Grammar.ie',
        description: 'Complete guide to Irish prepositions (Réamhfhocail): simple prepositions, compound prepositions, genitive triggers, and prepositional pronouns.',
        gaName: 'An Réamhfhocal',
    },
    'prepositions/conjugated': {
        seoTitle: 'Conjugated Prepositions (Réamhfhocail Chónasctha) | Grammar.ie',
        description: 'Comprehensive guide to conjugated prepositions (prepositional pronouns) in Irish: ag, ar, le, do, de, ó, chuig, faoi, roimh, and more.',
        gaName: 'Réamhfhocail Chónasctha',
    },
    pronouns: {
        seoTitle: 'Pronouns (Forainmneacha) – Personal & Possessive | Grammar.ie',
        description: 'Guide to Irish pronouns (Forainmneacha): learn personal subject and object pronouns, possessive determiners, emphatic forms, and mutations.',
        gaName: 'An Forainm Pearsanta',
    },
    pronunciation: {
        seoTitle: 'Pronunciation & Orthography (Fuaimeanna & Litriú) | Grammar.ie',
        description: 'Guide to Irish pronunciation, spelling conventions, broad and slender consonants (caol le caol), stress patterns, and phonetic systems.',
        gaName: 'Fuaimeanna agus Litriú',
    },
    syntax: {
        seoTitle: 'Syntax & Sentence Structure (An Chómhréir) | Grammar.ie',
        description: 'Learn Irish sentence structure (Verb-Subject-Object order), relative clauses, conjunctions, conditional sentences, emphasis, and reported speech.',
        gaName: 'An Chómhréir',
    },
    verbs: {
        seoTitle: 'Verbs (An Briathar) – Tenses, Conjugations & Forms | Grammar.ie',
        description: 'Complete reference for Irish verbs (An Briathar): regular first and second conjugations, irregular verbs, tenses, moods, and verbal nouns.',
        gaName: 'An Briathar',
    },
    'verbs/conjugations': {
        seoTitle: 'Verb Conjugations – First & Second Conjugation Rules | Grammar.ie',
        description: 'Learn regular Irish verb conjugations: first conjugation (-áil, -igh, monosyllabic) and second conjugation (-aigh/-igh, polysyllabic) across all tenses.',
        gaName: 'Réimnithe na mBriathra',
    },
    'verbs/irregular': {
        seoTitle: 'The 11 Irregular Verbs (Briathra Neamhrialta) | Grammar.ie',
        description: 'Complete conjugation guide to the 11 irregular Irish verbs (bí, abair, beir, clois, déan, faigh, feic, ith, tabhair, tar, téigh) across all tenses.',
        gaName: 'Briathra Neamhrialta',
    },
    'verbs/verbal-noun': {
        seoTitle: 'Verbal Nouns (Ainm Briathartha) – Syntax & Progressive Aspect | Grammar.ie',
        description: 'Master Irish verbal nouns (ainm briathartha): progressive structures with ag, passive forms with á, genitive object constructions, and syntax.',
        gaName: 'An tAinm Briathartha',
    },
};

const categoryNames: Record<string, string> = {
    nouns: 'Nouns',
    verbs: 'Verbs',
    mutations: 'Mutations',
    prepositions: 'Prepositions',
    adjectives: 'Adjectives',
    adverbs: 'Adverbs',
    articles: 'Articles',
    copula: 'Copula',
    numbers: 'Numbers',
    pronouns: 'Pronouns',
    pronunciation: 'Pronunciation',
    syntax: 'Syntax',
    other: 'Grammar',
};

export function getCanonicalUrl(pathname: string, siteUrl = defaultSeo.siteUrl): string {
    const cleanPath = pathname.replace(/\/+$/, '');
    return cleanPath ? `${siteUrl}${cleanPath}/` : `${siteUrl}/`;
}

export function getCategoryName(rootSegment: string): string {
    return categoryNames[rootSegment] || 'Irish Grammar';
}

export function buildArticleTitle(entry: GrammarEntry, currentPath: string): string {
    const customSeoTitle = (entry.data as Record<string, unknown>).seoTitle;
    if (typeof customSeoTitle === 'string' && customSeoTitle.trim()) {
        return customSeoTitle.trim();
    }

    const en = entry.data.enTitle?.trim() || '';
    const ga = entry.data.gaTitle?.trim() || '';
    const parts = currentPath.split('/');
    const root = parts[0];
    const cat = getCategoryName(root);
    const isOverview = en.toLowerCase() === 'overview';

    if (isOverview) {
        if (currentPath === 'nouns/declensions/overview') {
            return 'Noun Declensions: Overview | Grammar.ie';
        }
        if (currentPath === 'verbs/conjugations/overview') {
            return 'Verb Conjugations: Overview | Grammar.ie';
        }
        if (currentPath === 'verbs/verbal-noun/overview') {
            return 'Verbal Nouns: Overview (Ainm Briathartha) | Grammar.ie';
        }
        const gaSnippet = ga ? ` (${ga})` : '';
        return `${cat}: Overview${gaSnippet} | Grammar.ie`;
    }

    if (currentPath.startsWith('verbs/irregular/')) {
        const verb = en.replace(/\s*\(.*\)/, '').trim();
        const meaningMatch = en.match(/\((.*?)\)/);
        const meaning = meaningMatch ? meaningMatch[1].trim() : '';
        const meaningSnippet = meaning ? ` (${meaning})` : '';
        return `${verb}${meaningSnippet} – Irregular Verbs | Grammar.ie`;
    }

    if (currentPath.startsWith('prepositions/conjugated/')) {
        return `${en} – Conjugated Prepositions | Grammar.ie`;
    }

    if (currentPath.startsWith('nouns/declensions/')) {
        const gaSnippet = ga && ga.toLowerCase() !== en.toLowerCase() ? ` (${ga})` : '';
        return `${en}${gaSnippet} – Noun Declensions | Grammar.ie`;
    }

    const enLower = en.toLowerCase();
    const rootLower = root.toLowerCase();
    const gaSnippet = (ga && ga.toLowerCase() !== enLower && !enLower.includes(ga.toLowerCase())) ? ` (${ga})` : '';

    if (enLower.includes(rootLower)) {
        return `${en}${gaSnippet} | Grammar.ie`;
    }

    return `${en}${gaSnippet} – ${cat} | Grammar.ie`;
}

export function getArticleSEO(entry: GrammarEntry, currentPath: string, canonicalUrl: string) {
    const seoTitle = buildArticleTitle(entry, currentPath);
    const customDesc = (entry.data as Record<string, unknown>).seoDescription;
    const description = (typeof customDesc === 'string' && customDesc.trim()) ? customDesc.trim() : (entry.data.description || defaultSeo.description);

    const parts = currentPath.split('/');
    const root = parts[0];
    const category = getCategoryName(root);

    const tags = entry.data.tags || [];
    const keywords = Array.from(new Set([
        ...tags,
        'Irish grammar',
        'Gramadach na Gaeilge',
        'Gaeilge',
        category,
        entry.data.enTitle,
        entry.data.gaTitle,
    ].filter(Boolean) as string[]));

    const schema = buildArticleJsonLd(canonicalUrl, seoTitle, description, keywords, category);

    return {
        seoTitle,
        description,
        keywords,
        schema,
    };
}

export function getFolderSEO(folderPath: string, displayTitle: string, childrenCount: number, canonicalUrl: string) {
    const predefined = folderSeoData[folderPath];
    const seoTitle = predefined?.seoTitle || `Irish ${displayTitle} – Grammar Guide | Grammar.ie`;
    const description = predefined?.description || `Explore Irish ${displayTitle} with ${childrenCount} structured grammar guides, rules, and examples on Grammar.ie.`;
    const root = folderPath.split('/')[0];
    const category = getCategoryName(root);

    const keywords = [
        'Irish grammar',
        'Gramadach na Gaeilge',
        'Gaeilge',
        displayTitle,
        category,
        predefined?.gaName,
    ].filter(Boolean) as string[];

    const schema = buildCollectionJsonLd(canonicalUrl, seoTitle, description, childrenCount);

    return {
        seoTitle,
        description,
        keywords,
        schema,
    };
}

export function buildBreadcrumbsJsonLd(
    breadcrumbs: BreadcrumbItem[],
    canonicalUrl: string,
) {
    const items = [
        {
            '@type': 'ListItem',
            position: 1,
            name: 'Home',
            item: `${defaultSeo.siteUrl}/`,
        },
    ];

    breadcrumbs.forEach((crumb, index) => {
        if (crumb.url === '/' || crumb.title.toLowerCase() === 'home') return;

        const isLast = index === breadcrumbs.length - 1;
        const itemUrl = isLast
            ? canonicalUrl
            : (crumb.url.startsWith('http') ? crumb.url : `${defaultSeo.siteUrl}${crumb.url.replace(/\/+$/, '')}/`);

        items.push({
            '@type': 'ListItem',
            position: items.length + 1,
            name: crumb.title,
            item: itemUrl,
        });
    });

    return {
        '@context': 'https://schema.org',
        '@type': 'BreadcrumbList',
        itemListElement: items,
    };
}

export function buildArticleJsonLd(
    canonicalUrl: string,
    headline: string,
    description: string,
    keywords: string[] = [],
    section?: string,
) {
    return {
        '@context': 'https://schema.org',
        '@type': 'TechArticle',
        headline,
        description,
        url: canonicalUrl,
        mainEntityOfPage: {
            '@type': 'WebPage',
            '@id': canonicalUrl,
        },
        image: defaultSeo.ogImage,
        inLanguage: ['en', 'ga'],
        educationalLevel: 'All levels',
        learningResourceType: 'Grammar Reference',
        keywords: keywords.join(', '),
        publisher: {
            '@type': 'Organization',
            name: 'Grammar.ie',
            url: `${defaultSeo.siteUrl}/`,
            logo: {
                '@type': 'ImageObject',
                url: `${defaultSeo.siteUrl}/favicon.svg`,
            },
        },
        about: [
            {
                '@type': 'Thing',
                name: section ? `${section} (Irish Grammar)` : 'Irish Grammar',
            },
            {
                '@type': 'Thing',
                name: 'Gramadach na Gaeilge',
            },
        ],
    };
}

export function buildCollectionJsonLd(
    canonicalUrl: string,
    name: string,
    description: string,
    itemsCount?: number,
) {
    return {
        '@context': 'https://schema.org',
        '@type': 'CollectionPage',
        name,
        description,
        url: canonicalUrl,
        inLanguage: ['en', 'ga'],
        publisher: {
            '@type': 'Organization',
            name: 'Grammar.ie',
            url: `${defaultSeo.siteUrl}/`,
            logo: {
                '@type': 'ImageObject',
                url: `${defaultSeo.siteUrl}/favicon.svg`,
            },
        },
        ...(itemsCount !== undefined ? { numberOfItems: itemsCount } : {}),
    };
}

export const websiteJsonLd = {
    '@context': 'https://schema.org',
    '@type': 'WebSite',
    name: 'Grammar.ie',
    alternateName: ['Gramadach na Gaeilge', 'Grammar IE', 'Irish Grammar Guide'],
    url: `${defaultSeo.siteUrl}/`,
    description: defaultSeo.description,
    inLanguage: ['en', 'ga'],
    publisher: {
        '@type': 'Organization',
        name: 'Grammar.ie',
        url: `${defaultSeo.siteUrl}/`,
        logo: {
            '@type': 'ImageObject',
            url: `${defaultSeo.siteUrl}/favicon.svg`,
        },
    },
};

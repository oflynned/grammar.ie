import type {CollectionEntry} from 'astro:content';

export type GrammarEntry = CollectionEntry<'grammar'>;

export type TreeChild = {
    slug: string;
    title: string;
    href: string;
    kind: 'folder' | 'page';
    description?: string;
    count?: number;
    order?: number;
}

export function entryPath(entry: {id: string}) {
    return entry.id.replace(/\.(md|mdx)$/, '');
}

export const moduleMetadata: Record<string, {ga: string; order: number}> = {
    nouns: {ga: 'AN tAINMFHOCAL', order: 10},
    articles: {ga: 'AN CÓNASC', order: 20},
    adjectives: {ga: 'AN AIDIACHT', order: 30},
    verbs: {ga: 'AN BRIATHAR', order: 40},
    adverbs: {ga: 'AN DOBRIATHAR', order: 50},
    prepositions: {ga: 'AN RÉAMHFHOCAL', order: 60},
    pronouns: {ga: 'AN FORAINM PEARSANTA', order: 70},
    syntax: {ga: 'AN CHÓMHRÉIR', order: 80},
    'initial-mutations': {ga: 'NA hATHRUITHE TOSAIGH', order: 90},
    numbers: {ga: 'NA hUIMHREACHA', order: 100},
    pronunciation: {ga: 'FUAIMEANNA AGUS LITRIÚ', order: 110},
    other: {ga: 'EILE', order: 999},
}

const labelOverrides: Record<string, string> = {
    bi: 'Bí',
    conjugated: 'Conjugated Prepositions',
    dean: 'Déan',
    i: 'i',
    o: 'Ó',
    tri: 'Trí',
}

export function formatSegment(name: string) {
    if (labelOverrides[name]) return labelOverrides[name];

    return name
        .replace(/-/g, ' ')
        .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function descendantsForPath(entries: GrammarEntry[], path: string) {
    const prefix = path ? `${path}/` : '';

    return entries.filter((entry) => {
        const routePath = entryPath(entry);

        return routePath.startsWith(prefix) && routePath !== path;
    });
}

function mostCommon(values: Array<string | undefined>) {
    const counts = values.reduce<Map<string, number>>((acc, value) => {
        if (!value) return acc;

        acc.set(value, (acc.get(value) ?? 0) + 1);
        return acc;
    }, new Map());

    return Array.from(counts.entries()).toSorted((a, b) => b[1] - a[1]).at(0)?.[0];
}

export function titleForPath(entries: GrammarEntry[], path: string) {
    const segment = path.split('/').at(-1) ?? path;
    if (!path.includes('/') && moduleMetadata[path]) return formatSegment(path);

    const descendants = descendantsForPath(entries, path);
    const metadataTitle = mostCommon(descendants.flatMap((entry) => [
        entry.data.topicSlug === segment ? entry.data.topic : undefined,
        entry.data.sectionSlug === segment ? entry.data.section : undefined,
    ]));

    return metadataTitle ?? formatSegment(segment);
}

export function directChildrenForPath(entries: GrammarEntry[], path: string): TreeChild[] {
    const prefix = path ? `${path}/` : '';
    const folderCounts = new Map<string, number>();
    const pages: GrammarEntry[] = [];

    for (const entry of entries) {
        const routePath = entryPath(entry);
        if (!routePath.startsWith(prefix) || routePath === path) continue;

        const remainder = routePath.slice(prefix.length);
        const [nextSegment, ...rest] = remainder.split('/');

        if (rest.length === 0) {
            pages.push(entry);
            continue;
        }

        const folderPath = `${prefix}${nextSegment}`;
        folderCounts.set(folderPath, (folderCounts.get(folderPath) ?? 0) + 1);
    }

    const folders = Array.from(folderCounts.entries()).map<TreeChild>(([folderPath, count]) => {
        const rootSlug = folderPath.split('/')[0];

        return {
            slug: folderPath,
            title: titleForPath(entries, folderPath),
            href: `/${folderPath}`,
            kind: 'folder',
            count,
            order: moduleMetadata[rootSlug]?.order,
        };
    });

    const pageChildren = pages.map<TreeChild>((entry) => ({
        slug: entryPath(entry),
        title: entry.data.navTitle ?? entry.data.title ?? formatSegment(entryPath(entry).split('/').at(-1) ?? entryPath(entry)),
        href: `/${entryPath(entry)}`,
        kind: 'page',
        description: entry.data.description,
        order: entry.data.order,
    }));

    return [...folders, ...pageChildren].toSorted((a, b) => {
        if (a.kind !== b.kind) return a.kind === 'folder' ? -1 : 1;

        const orderDifference = (a.order ?? 999) - (b.order ?? 999);
        if (orderDifference) return orderDifference;

        return a.title.localeCompare(b.title);
    });
}

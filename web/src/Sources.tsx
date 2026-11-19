import type { Passage } from './api';

export function groupSources(passages: Passage[]) {
  const documents = new Map<string, { title: string; filename: string | null; passages: Passage[] }>();
  for (const passage of passages) {
    const key = passage.source ? `document:${passage.source}` : `passage:${passage.id}`;
    const document = documents.get(key);
    if (document) {
      document.passages.push(passage);
      continue;
    }

    const title = passage.source
      ?.replace(/^(news|research|engineering|announcements)_/i, '')
      .replace(/\.md$/i, '')
      .replace(/[-_]+/g, ' ')
      .trim();

    documents.set(key, {
      title: title ? title[0].toUpperCase() + title.slice(1) : 'Untitled document',
      filename: passage.source,
      passages: [passage],
    });
  }

  return Array.from(documents, ([key, document]) => ({ key, ...document }));
}

export function Sources({ documents }: { documents: ReturnType<typeof groupSources> }) {
  return (
    <div className="source-list">
      {documents.map(({ key, title, passages }) => (
        <details className="source" key={key}>
          <summary>
            {title}<small>{passages.length} {passages.length === 1 ? 'passage' : 'passages'}</small>
          </summary>
          <div className="passages">
            {passages.map((passage) => <p key={passage.id}>{passage.content}</p>)}
          </div>
        </details>
      ))}
    </div>
  );
}

export function SourceDocuments({ documents }: { documents: ReturnType<typeof groupSources> }) {
  return (
    <ul className="source-list original-documents">
      {documents.map(({ key, title, filename }) => (
        <li className="source" key={key}>
          <span className="document-icon" aria-hidden="true">≡</span>
          <div>
            <strong>{title}</strong>
            {filename && <small>{filename}</small>}
          </div>
        </li>
      ))}
    </ul>
  );
}

import { memo, useMemo } from 'react';
import { diffLines, Change } from 'diff';
import { cn } from '@/lib/utils';

interface DiffViewerProps {
  /** Original content */
  oldContent: string;
  /** New content */
  newContent: string;
  /** File path for display */
  filePath?: string;
  /** CSS className */
  className?: string;
}

/**
 * DiffViewer displays file content differences with syntax highlighting.
 * Uses the diff library to compute line-by-line differences.
 */
export const DiffViewer = memo(function DiffViewer({
  oldContent,
  newContent,
  filePath,
  className,
}: DiffViewerProps) {
  const diff = useMemo(() => {
    return diffLines(oldContent, newContent);
  }, [oldContent, newContent]);

  const stats = useMemo(() => {
    let additions = 0;
    let deletions = 0;
    diff.forEach((part) => {
      if (part.added) {
        additions += part.count || 0;
      } else if (part.removed) {
        deletions += part.count || 0;
      }
    });
    return { additions, deletions };
  }, [diff]);

  return (
    <div className={cn('rounded-lg border overflow-hidden text-sm', className)}>
      {/* Header */}
      {filePath && (
        <div className="flex items-center justify-between px-3 py-2 bg-muted/50 border-b">
          <span className="font-mono text-xs text-muted-foreground">{filePath}</span>
          <div className="flex items-center gap-2 text-xs">
            <span className="text-green-600">+{stats.additions}</span>
            <span className="text-red-600">-{stats.deletions}</span>
          </div>
        </div>
      )}

      {/* Diff content */}
      <div className="font-mono text-xs overflow-x-auto">
        {diff.map((part: Change, index: number) => {
          const bgColor = part.added
            ? 'bg-green-50 dark:bg-green-950/30'
            : part.removed
              ? 'bg-red-50 dark:bg-red-950/30'
              : 'transparent';
          const textColor = part.added
            ? 'text-green-700 dark:text-green-400'
            : part.removed
              ? 'text-red-700 dark:text-red-400'
              : 'text-muted-foreground';
          const prefix = part.added ? '+' : part.removed ? '-' : ' ';

          return (
            <div
              key={index}
              className={cn('flex px-2 py-0.5', bgColor)}
            >
              <span className="w-6 flex-shrink-0 select-none opacity-50">{prefix}</span>
              <pre className={cn('whitespace-pre-wrap break-all flex-1', textColor)}>
                {part.value}
              </pre>
            </div>
          );
        })}
      </div>
    </div>
  );
});

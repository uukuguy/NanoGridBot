import { memo, useState } from 'react';
import { Copy, Check, ChevronDown, ChevronUp, Play, CheckCircle2, XCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ToolCall {
  id: string;
  function: {
    name: string;
    arguments: string | Record<string, unknown>;
  };
}

interface ToolCallCardProps {
  toolCall: ToolCall;
  /** Tool output (optional, shown when tool completes) */
  output?: unknown;
  /** Whether this tool call is currently running */
  isRunning?: boolean;
  /** Whether the tool call succeeded or failed (null if still running) */
  status?: 'success' | 'error' | null;
  /** Click handler to show full details in Inspector */
  onClick?: () => void;
  /** CSS className */
  className?: string;
}

/**
 * ToolCallCard displays a compact tool call card with expandable arguments.
 * Click to show full details in the Inspector panel.
 */
export const ToolCallCard = memo(function ToolCallCard({
  toolCall,
  output,
  isRunning = false,
  status = null,
  onClick,
  className,
}: ToolCallCardProps) {
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState(false);

  const functionName = toolCall.function.name;
  const arguments_ = toolCall.function.arguments;

  // Parse arguments if it's a string
  const argsDisplay = typeof arguments_ === 'string'
    ? arguments_
    : JSON.stringify(arguments_, null, 2);

  // Parse output if it's a string
  const outputDisplay = output
    ? typeof output === 'string'
      ? output
      : JSON.stringify(output, null, 2)
    : null;

  const handleCopy = async (e: React.MouseEvent) => {
    e.stopPropagation();
    await navigator.clipboard.writeText(argsDisplay);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const statusIcon = isRunning ? (
    <Play className="w-3 h-3 animate-spin text-blue-500" />
  ) : status === 'success' ? (
    <CheckCircle2 className="w-3 h-3 text-green-500" />
  ) : status === 'error' ? (
    <XCircle className="w-3 h-3 text-red-500" />
  ) : null;

  const borderColor = isRunning
    ? 'border-blue-200 dark:border-blue-800'
    : status === 'success'
      ? 'border-green-200 dark:border-green-800'
      : status === 'error'
        ? 'border-red-200 dark:border-red-800'
        : 'border-muted';

  return (
    <div
      className={cn(
        'rounded-lg border bg-card transition-colors',
        borderColor,
        onClick && 'cursor-pointer hover:bg-muted/50',
        className
      )}
      onClick={onClick}
    >
      {/* Header */}
      <div
        className="flex items-center gap-2 px-3 py-2 cursor-pointer"
        onClick={(e) => {
          e.stopPropagation();
          setExpanded(!expanded);
        }}
      >
        {statusIcon}
        <span className="font-mono text-xs font-medium text-blue-600 dark:text-blue-400">
          {functionName}
        </span>
        <span className="flex-1" />
        <button
          onClick={handleCopy}
          className="p-1 hover:bg-muted rounded opacity-60 hover:opacity-100"
          title="Copy arguments"
        >
          {copied ? <Check className="w-3 h-3 text-green-500" /> : <Copy className="w-3 h-3" />}
        </button>
        {expanded ? (
          <ChevronUp className="w-3 h-3 opacity-60" />
        ) : (
          <ChevronDown className="w-3 h-3 opacity-60" />
        )}
      </div>

      {/* Arguments (collapsed) */}
      {!expanded && (
        <div className="px-3 pb-2">
          <pre className="text-xs text-muted-foreground truncate font-mono">
            {argsDisplay.slice(0, 100)}
            {argsDisplay.length > 100 ? '...' : ''}
          </pre>
        </div>
      )}

      {/* Arguments (expanded) */}
      {expanded && (
        <div className="px-3 pb-3 border-t border-muted">
          <div className="mt-2">
            <div className="text-xs font-medium text-muted-foreground mb-1">Arguments</div>
            <pre className="text-xs font-mono bg-muted/50 rounded p-2 overflow-x-auto whitespace-pre-wrap break-all">
              {argsDisplay}
            </pre>
          </div>

          {/* Output */}
          {outputDisplay && (
            <div className="mt-2">
              <div className="text-xs font-medium text-muted-foreground mb-1">Output</div>
              <pre className="text-xs font-mono bg-muted/50 rounded p-2 overflow-x-auto whitespace-pre-wrap break-all max-h-48">
                {outputDisplay}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
});

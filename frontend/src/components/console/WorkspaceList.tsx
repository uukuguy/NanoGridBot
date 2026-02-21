import { useState, useMemo, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, FolderOpen } from 'lucide-react';
import { useChatStore } from '../../stores/chat';
import { Button } from '@/components/ui/button';
import { SearchInput } from '@/components/common';
import { CreateContainerDialog } from '@/components/chat/CreateContainerDialog';
import { SkeletonCardList } from '@/components/common/Skeletons';
import { cn } from '@/lib/utils';

interface WorkspaceListProps {
  className?: string;
  onWorkspaceSelect?: (jid: string, folder: string) => void;
}

export function WorkspaceList({ className, onWorkspaceSelect }: WorkspaceListProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [createOpen, setCreateOpen] = useState(false);

  const {
    groups,
    currentGroup,
    selectGroup,
    loadGroups,
    loading,
  } = useChatStore();
  const navigate = useNavigate();

  useEffect(() => {
    loadGroups();
  }, [loadGroups]);

  // Separate home group from others, sort by time
  const { mainGroup, otherGroups } = useMemo(() => {
    let main: (typeof groups)[string] & { jid: string } | null = null;
    const others: ((typeof groups)[string] & { jid: string })[] = [];

    for (const [jid, info] of Object.entries(groups)) {
      const entry = { jid, ...info };
      if (info.is_my_home) {
        main = entry;
      } else {
        others.push(entry);
      }
    }

    others.sort((a, b) => {
      const timeA = a.lastMessageTime || a.added_at;
      const timeB = b.lastMessageTime || b.added_at;
      return new Date(timeB).getTime() - new Date(timeA).getTime();
    });

    return { mainGroup: main, otherGroups: others };
  }, [groups]);

  // Filter by search query
  const filteredGroups = useMemo(() => {
    if (!searchQuery.trim()) return otherGroups;
    return otherGroups.filter((g) =>
      g.name.toLowerCase().includes(searchQuery.toLowerCase())
    );
  }, [otherGroups, searchQuery]);

  const handleGroupSelect = (jid: string, folder: string) => {
    selectGroup(jid);
    if (onWorkspaceSelect) {
      onWorkspaceSelect(jid, folder);
    } else {
      navigate(`/chat/${folder}`);
    }
  };

  const handleCreated = (jid: string, folder: string) => {
    selectGroup(jid);
    if (onWorkspaceSelect) {
      onWorkspaceSelect(jid, folder);
    } else {
      navigate(`/chat/${folder}`);
    }
  };

  const allGroups = mainGroup ? [mainGroup, ...filteredGroups] : filteredGroups;

  return (
    <div className={cn('flex flex-col h-full bg-background border-r', className)}>
      {/* Header */}
      <div className="p-3 space-y-2">
        <Button
          variant="outline"
          className="w-full justify-start gap-2"
          onClick={() => setCreateOpen(true)}
        >
          <Plus className="w-4 h-4" />
          新建
        </Button>
        <SearchInput
          value={searchQuery}
          onChange={setSearchQuery}
          placeholder="搜索..."
          debounce={200}
        />
      </div>

      {/* Workspace List */}
      <div className="flex-1 overflow-y-auto px-2 pb-2">
        {loading && allGroups.length === 0 ? (
          <SkeletonCardList count={5} compact />
        ) : allGroups.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-32 px-4">
            <FolderOpen className="w-8 h-8 text-muted-foreground mb-2" />
            <p className="text-sm text-muted-foreground text-center">
              {searchQuery ? '无匹配结果' : '暂无工作区'}
            </p>
          </div>
        ) : (
          <div className="space-y-0.5">
            {/* Home workspace first */}
            {mainGroup && (
              <WorkspaceItem
                jid={mainGroup.jid}
                name={mainGroup.name}
                folder={mainGroup.folder}
                isActive={currentGroup === mainGroup.jid}
                isHome
                onSelect={handleGroupSelect}
              />
            )}

            {/* Other workspaces */}
            {filteredGroups.map((group) => (
              <WorkspaceItem
                key={group.jid}
                jid={group.jid}
                name={group.name}
                folder={group.folder}
                isActive={currentGroup === group.jid}
                onSelect={handleGroupSelect}
              />
            ))}
          </div>
        )}
      </div>

      {/* Create Dialog */}
      <CreateContainerDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={handleCreated}
      />
    </div>
  );
}

// Workspace item component
interface WorkspaceItemProps {
  jid: string;
  name: string;
  folder: string;
  isActive: boolean;
  isHome?: boolean;
  onSelect: (jid: string, folder: string) => void;
}

function WorkspaceItem({
  jid,
  name,
  folder,
  isActive,
  isHome,
  onSelect,
}: WorkspaceItemProps) {
  const waiting = useChatStore((s) => s.waiting);
  const isRunning = !!waiting[jid];

  return (
    <button
      onClick={() => onSelect(jid, folder)}
      className={cn(
        'w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-left transition-colors',
        isActive
          ? 'bg-primary/10 text-primary'
          : 'hover:bg-accent text-foreground'
      )}
    >
      {/* Status indicator */}
      <span
        className={cn(
          'w-2 h-2 rounded-full flex-shrink-0',
          isRunning ? 'bg-emerald-500 animate-pulse' : 'bg-slate-400'
        )}
      />

      {/* Name */}
      <span className="flex-1 truncate text-sm font-medium">
        {name}
      </span>

      {/* Home badge */}
      {isHome && (
        <span className="text-[10px] px-1 py-0.5 rounded bg-primary/20 text-primary">
          主
        </span>
      )}
    </button>
  );
}

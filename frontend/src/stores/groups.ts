import { create } from 'zustand';
import { api } from '../api/adapter';
import type { FrontendGroupInfo } from '../api/adapter';

export type { FrontendGroupInfo as GroupInfo };

interface GroupsState {
  groups: Record<string, FrontendGroupInfo>;
  loading: boolean;
  error: string | null;
  loadGroups: () => Promise<void>;
}

export const useGroupsStore = create<GroupsState>((set) => ({
  groups: {},
  loading: false,
  error: null,

  loadGroups: async () => {
    set({ loading: true });
    try {
      const data = await api.getGroups();
      set({ groups: data.groups, loading: false, error: null });
    } catch (err) {
      set({ loading: false, error: err instanceof Error ? err.message : String(err) });
    }
  },
}));

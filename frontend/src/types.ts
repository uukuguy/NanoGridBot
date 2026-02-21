export interface GroupInfo {
  jid?: string;
  name: string;
  folder: string;
  added_at?: string;
  active?: boolean;
  kind?: 'home' | 'main' | 'feishu' | 'web';
  is_home?: boolean;
  is_my_home?: boolean;
  editable?: boolean;
  deletable?: boolean;
  lastMessage?: string;
  lastMessageTime?: string;
  execution_mode?: 'container' | 'host';
  custom_cwd?: string;
  created_by?: string;
  selected_skills?: string[] | null;
}

export type Role = 'viewer' | 'member' | 'lead' | 'admin';

export type ItemStatus = 'open' | 'in_progress' | 'pending_approval' | 'resolved' | 'closed';

export type ItemPriority = 'low' | 'medium' | 'high' | 'critical';

export interface User {
  id: string;
  email: string;
  name: string;
  is_active: boolean;
  created_at: string;
  teams?: TeamMembership[];
}

export interface TeamMembership {
  team_id: string;
  team_name: string;
  team_slug: string;
  role: Role;
}

export interface Team {
  id: string;
  name: string;
  slug: string;
  my_role?: Role;
}

export interface WorkItem {
  id: string;
  team_id: string;
  title: string;
  description: string | null;
  status: ItemStatus;
  priority: ItemPriority;
  assignee_id: string | null;
  assignee_name?: string | null;
  created_by: string;
  creator_name?: string | null;
  requires_approval: boolean;
  approved_by: string | null;
  approved_at: string | null;
  due_at: string | null;
  version: number;
  created_at: string;
  updated_at: string;
  allowed_actions: string[];
}

export interface ItemListResponse {
  items: WorkItem[];
  next_cursor: string | null;
  total_estimate?: number | null;
}

export interface ItemEvent {
  id: number;
  item_id: string;
  actor_id: string;
  actor_name?: string | null;
  type: string;
  payload: Record<string, any> | null;
  created_at: string;
}

export interface EventListResponse {
  events: ItemEvent[];
  next_cursor: string | null;
}

export interface Comment {
  id: string;
  item_id: string;
  author_id: string;
  author_name?: string | null;
  body: string;
  created_at: string;
}

export interface DashboardSection {
  label: string;
  items: WorkItem[];
  count: number;
}

export interface DashboardResponse {
  sections: DashboardSection[];
  status_counts: Record<string, number>;
}

export interface Notification {
  id: string;
  user_id: string;
  item_id: string | null;
  kind: string;
  read_at: string | null;
  created_at: string;
}

export interface NotificationListResponse {
  notifications: Notification[];
  unread_count: number;
}

export interface ApiError {
  code: string;
  message: string;
  request_id?: string;
}

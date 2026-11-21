import {
  Comment,
  DashboardResponse,
  EventListResponse,
  ItemListResponse,
  NotificationListResponse,
  Team,
  User,
  WorkItem,
} from '../types';

export class ApiError extends Error {
  code: string;
  status: number;
  requestId?: string;
  currentData?: any;

  constructor(status: number, code: string, message: string, requestId?: string, currentData?: any) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.requestId = requestId;
    this.currentData = currentData;
  }
}

export function generateUUID(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers || {});
  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(endpoint, {
    ...options,
    headers,
    credentials: 'include',
  });

  if (response.status === 204) {
    return {} as T;
  }

  let data: any;
  try {
    data = await response.json();
  } catch {
    data = null;
  }

  if (!response.ok) {
    const code = data?.error?.code || (response.status === 409 ? 'conflict' : 'error');
    const message = data?.error?.message || data?.detail || `HTTP ${response.status} Error`;
    const requestId = data?.error?.request_id || response.headers.get('X-Request-Id') || undefined;
    throw new ApiError(response.status, code, message, requestId, data);
  }

  return data as T;
}

export const api = {
  auth: {
    login: (email: string, password: string) =>
      request<User>('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      }),
    logout: () =>
      request<{ status: string }>('/auth/logout', {
        method: 'POST',
      }),
    me: () => request<User>('/auth/me'),
  },

  teams: {
    list: () => request<Team[]>('/teams'),
  },

  items: {
    list: (params: {
      team_id?: string;
      status?: string;
      priority?: string;
      assignee_id?: string;
      q?: string;
      cursor?: string;
      limit?: number;
    }) => {
      const searchParams = new URLSearchParams();
      if (params.team_id) searchParams.set('team_id', params.team_id);
      if (params.status) searchParams.set('status', params.status);
      if (params.priority) searchParams.set('priority', params.priority);
      if (params.assignee_id) searchParams.set('assignee_id', params.assignee_id);
      if (params.q) searchParams.set('q', params.q);
      if (params.cursor) searchParams.set('cursor', params.cursor);
      if (params.limit) searchParams.set('limit', String(params.limit));

      const queryStr = searchParams.toString();
      return request<ItemListResponse>(`/items${queryStr ? `?${queryStr}` : ''}`);
    },

    get: (id: string) => request<WorkItem>(`/items/${id}`),

    create: (
      payload: {
        team_id: string;
        title: string;
        description?: string;
        priority?: string;
        requires_approval?: boolean;
        due_at?: string;
      },
      idempotencyKey: string = generateUUID()
    ) =>
      request<WorkItem>('/items', {
        method: 'POST',
        headers: { 'Idempotency-Key': idempotencyKey },
        body: JSON.stringify(payload),
      }),

    update: (
      id: string,
      payload: {
        title?: string;
        description?: string;
        priority?: string;
        requires_approval?: boolean;
        due_at?: string;
      },
      version: number
    ) =>
      request<WorkItem>(`/items/${id}`, {
        method: 'PATCH',
        headers: { 'If-Match': String(version) },
        body: JSON.stringify(payload),
      }),

    claim: (id: string) =>
      request<WorkItem>(`/items/${id}/claim`, {
        method: 'POST',
      }),

    assign: (id: string, assigneeId: string, version: number) =>
      request<WorkItem>(`/items/${id}/assign`, {
        method: 'POST',
        headers: { 'If-Match': String(version) },
        body: JSON.stringify({ assignee_id: assigneeId }),
      }),

    release: (id: string, version: number) =>
      request<WorkItem>(`/items/${id}/release`, {
        method: 'POST',
        headers: { 'If-Match': String(version) },
      }),

    transition: (id: string, to: string, version: number, comment?: string) =>
      request<WorkItem>(`/items/${id}/transition`, {
        method: 'POST',
        headers: { 'If-Match': String(version) },
        body: JSON.stringify({ to, comment: comment || undefined }),
      }),

    getComments: (id: string) => request<Comment[]>(`/items/${id}/comments`),

    addComment: (id: string, body: string) =>
      request<Comment>(`/items/${id}/comments`, {
        method: 'POST',
        body: JSON.stringify({ body }),
      }),

    getEvents: (id: string, cursor?: string, limit: number = 50) => {
      const searchParams = new URLSearchParams();
      if (cursor) searchParams.set('cursor', cursor);
      searchParams.set('limit', String(limit));
      return request<EventListResponse>(`/items/${id}/events?${searchParams.toString()}`);
    },
  },

  dashboard: {
    get: () => request<DashboardResponse>('/dashboard'),
  },

  notifications: {
    list: () => request<NotificationListResponse>('/notifications'),
    markRead: (id: string) =>
      request<Notification>(`/notifications/${id}/read`, {
        method: 'POST',
      }),
  },
};

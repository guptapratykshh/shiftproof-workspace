export type Role = "organization" | "supervisor" | "worker";
export type Base = { id: string; created_at: string; organization_id: string };
export type Membership = Base & {
  user_id: string;
  department_id: string;
  primary: boolean;
  backup: boolean;
  permissions: string[];
  active: boolean;
};
export type Person = Base & {
  name: string;
  role: Role;
  email: string | null;
  employee_code: string | null;
  phone: string;
  active: boolean;
  verified: boolean;
  preferences: {
    theme?: string;
    language?: string;
    speech_language?: string;
    notifications?: Record<string, boolean>;
  };
  profile: Record<string, string>;
  departments?: Membership[];
  teams?: (Base & { team_id: string; active: boolean })[];
  shifts?: ShiftAssignment[];
  skills?: {
    id: string;
    name: string;
    qualification: string;
    expires_on: string | null;
  }[];
  availability?: {
    id: string;
    starts_at: string;
    ends_at: string;
    status: string;
    reason: string;
  }[];
  activation_url?: string;
};
export type Organization = Base & {
  name: string;
  code: string;
  industry: string;
  contact: string;
  timezone: string;
  active: boolean;
  settings: Record<string, string | boolean | null>;
};
export type Session = {
  user: Person;
  organization: Organization;
  memberships: Membership[];
  teamMemberships: { team_id: string; active: boolean }[];
  offlineKey: string;
  session: { expiresAt: string; idleMinutes: number };
};
export type Department = Base & {
  name: string;
  description: string;
  active: boolean;
};
export type Team = Department & { department_id: string };
export type Shift = Base & {
  name: string;
  starts_at: string;
  ends_at: string;
  days: number[];
  rotation: Record<string, unknown>;
  grace_minutes: number;
  active: boolean;
  warnings?: string[];
};
export type ShiftAssignment = Base & {
  user_id: string;
  shift_id: string;
  department_id: string;
  starts_on: string;
  ends_on: string | null;
  active: boolean;
};
export type Paged<T> = { items: T[]; total: number };
export type History = Base & {
  action: string;
  actor_id: string;
  detail: Record<string, unknown>;
};
export type Task = Base & {
  title: string;
  description: string;
  instructions: string;
  department_id: string;
  team_id: string | null;
  shift_id: string | null;
  priority: string | null;
  critical: boolean;
  verification_required: boolean;
  status: string;
  deadline: string | null;
  started_at: string | null;
  completed_at: string | null;
  closed_at: string | null;
  assignment_type: string;
  required_skills: string[];
  blocked_reason: string;
  version: number;
  source_report_id: string | null;
  reports?: Report[];
  history?: History[];
  assignments?: {
    id: string;
    user_id: string | null;
    team_id: string | null;
    lead_id: string | null;
    ended_at: string | null;
    reason: string;
  }[];
  comments?: (Base & { author_id: string; text: string; internal: boolean })[];
  verifications?: (Base & {
    reviewer_id: string;
    approved: boolean;
    reason: string;
  })[];
  dependencies?: string[];
};
export type ReportFields = {
  category: string;
  description: string;
  machine?: string | null;
  work_area?: string | null;
  batch?: string | null;
  order?: string | null;
  task_reference?: string | null;
  product?: string | null;
  reference_period?: string | null;
  observation_time?: string | null;
  quantity_basis?: "total" | "additional" | null;
  quality_status?: "passed" | "rejected" | "pending" | null;
  dispatch_status?: "dispatched" | "pending" | null;
  machine_status?: "operational" | "maintenance" | "stopped" | "failed" | null;
  task_status?: "completed" | "pending" | null;
  quantity?: number | null;
  unit?: string | null;
  operational_status?: string | null;
  action_taken?: string | null;
  safety_implication?: string | null;
  quality_implication?: string | null;
  uncertainty?: string[];
  suggested_task_id?: string | null;
};
export type ReportPayload = {
  client_request_id: string;
  department_id: string;
  team_id: string | null;
  shift_id: string | null;
  occurred_at: string;
  text: string;
  fields: ReportFields;
  task_id: string | null;
  transcript_id: string | null;
  extraction_id: string | null;
  evidence_ids: string[];
  immediate_safety: boolean;
  immediate_alert_id?: string | null;
  confirmed: true;
};
export type Asset = Base & {
  name: string;
  kind: string;
  mime_type: string;
  byte_size: number;
  deleted_at: string | null;
  retention_until: string;
};
export type Clarification = Base & {
  report_id: string;
  question: string;
  response: string | null;
  response_type: string | null;
  responded_at: string | null;
  recipient_id: string;
};
export type ReportVersion = Base & {
  number: number;
  text: string;
  fields: ReportFields;
  author_id: string;
  correction_reason: string;
  evidence: Asset[];
  transcript: {
    id: string;
    original: string;
    asset_id: string | null;
    provider: string;
    model: string;
  } | null;
  extraction: {
    id: string;
    input_text: string;
    output: ReportFields;
    provider: string;
    model: string;
  } | null;
};
export type Report = Base & {
  author_id: string;
  department_id: string;
  team_id: string | null;
  shift_id: string | null;
  occurred_at: string;
  submitted_at: string;
  category: string;
  status: string;
  immediate_safety: boolean;
  needs_attention: boolean;
  verified_at: string | null;
  resolved_at: string | null;
  latest_version: number;
  version: number;
  versions?: ReportVersion[];
  reviews?: (Base & {
    action: string;
    note: string;
    reviewer_id: string;
    version_number: number;
  })[];
  clarifications?: Clarification[];
  task_links?: { task_id: string; follow_up: boolean }[];
  conflict_ids?: string[];
};
export type AlertRecord = Base & {
  department_id: string;
  report_id: string | null;
  task_id: string | null;
  title: string;
  severity: string;
  status: string;
  assigned_to: string | null;
  acknowledged_at: string | null;
  resolution: string;
  escalation_level: number;
  version: number;
  history?: History[];
};
export type Conflict = Base & {
  title: string;
  discrepancy: string;
  status: string;
  resolution: string;
  department_id: string;
  version: number;
  reports?: (Report & { linked_version: number })[];
  findings?: {
    category: string;
    title: string;
    severity: string;
    values: (string | number)[];
    difference?: number;
    difference_unit?: string | null;
    recommended_action: string;
  }[];
};
export type HandoverItem = Base & {
  title: string;
  critical: boolean;
  source_type: string;
  source_id: string;
  detail: Record<string, unknown>;
  acknowledgements: (Base & { user_id: string })[];
};
export type HandoverVersion = Base & {
  number: number;
  provisional: boolean;
  changes: string;
  snapshot: {
    notes: string;
    compiled_at: string;
    pending_receipts: number;
    items: HandoverItem[];
  };
  items: HandoverItem[];
  recipients: { id: string; user_id: string; acknowledged_at: string | null }[];
};
export type Handover = Base & {
  department_id: string;
  shift_id: string;
  shift_date: string;
  status: string;
  latest_version: number;
  version: number;
  draft?: { notes: string; items: HandoverItem[] };
  versions?: HandoverVersion[];
};
export type Notification = Base & {
  title: string;
  body: string;
  href: string;
  read_at: string | null;
  category: string;
};
export type Job = Base & {
  kind: string;
  status: string;
  attempts: number;
  max_attempts: number;
  error: string;
  result: {
    text?: string;
    transcript_id?: string;
    extraction_id?: string;
    fields?: ReportFields;
    asset_id?: string;
    no_speech?: boolean;
    script?: string;
  };
  available_at: string;
};
export type MetricRow = Record<string, string | number | null>;
export type Analytics = {
  metrics: Record<string, number | null>;
  previous_metrics: Record<string, number | null>;
  trends: MetricRow[];
  departments: (MetricRow & { id: string; name: string; health: string })[];
  shifts: MetricRow[];
  teams: MetricRow[];
  task_status: MetricRow[];
  task_priority: MetricRow[];
  report_categories: MetricRow[];
  recurring_quality: MetricRow[];
  heatmap: MetricRow[];
  supervisor_workload: MetricRow[];
  handover_departments: MetricRow[];
  coverage: {
    department_id: string;
    department: string;
    primary: boolean;
    backup: boolean;
  }[];
  has_data: boolean;
  cohorts: Record<string, string>;
  period: { start: string; end: string; timezone: string };
};

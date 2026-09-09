export interface Tag {
  id: string;
  owner?: string;
  name: string;
  kind?: string;
  color: string;
  pinned?: boolean;
  is_system?: boolean;
  merged_into_id?: string | null;
  aliases?: string[];
  document_count?: number;
  created_at?: string;
}

export interface Folder {
  id: string;
  owner?: string;
  name: string;
  parent_id?: string | null;
  path?: string;
  document_count?: number;
  created_at?: string;
  children?: Folder[];
}

export interface ClassificationSummary {
  rule_id?: string | null;
  confidence: number;
  evidence?: Record<string, any> | null;
  suggested_tags: Tag[];
  suggested_fields: Record<string, any>;
}

export interface Document {
  id: string;
  owner: string;
  original_name: string;
  storage_key: string;
  mime_type: string;
  file_size: number;
  sha256: string;
  title?: string | null;
  sender?: string | null;
  document_date?: string | null;
  due_date?: string | null;
  amount?: number | null;
  amount_decimal?: string | null;
  currency?: string | null;
  source: string;
  metadata_revision: number;
  processing_state: string;
  classification_state: string;
  index_state: string;
  tags: Tag[];
  folders: Folder[];
  created_at: string;
  updated_at: string;
  pages?: DocumentPage[];
  assets?: any[];
  field_overrides?: Record<string, any>;
  classification?: ClassificationSummary | null;
}

export interface DocumentPage {
  page_number: number;
  extracted_text: string;
  extraction_method: string;
  ocr_confidence?: number | null;
  page_state: string;
  width?: number | null;
  height?: number | null;
  word_boxes?: any[] | null;
}

export interface SearchMatch {
  page_number: number;
  snippet: string;
  box?: {
    x0: number;
    y0: number;
    x1: number;
    y1: number;
  };
}

export interface DocumentSearchResult {
  documents: Document[];
  total: number;
  limit: number;
  offset: number;
  query: string;
}

export interface Job {
  job_id: string;
  job_type: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  progress: number;
  stage?: string | null;
  error_message?: string | null;
  document_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProcessingStatus {
  active_jobs: Job[];
  queued_count: number;
  running_count: number;
  total_active: number;
}

export interface UploadItem {
  item_id: string;
  filename: string;
  file_size: number;
  status: 'queued' | 'uploading' | 'processing' | 'completed' | 'failed';
  progress?: number;
  document_id?: string | null;
  error_message?: string | null;
  file?: File;
}

export interface UploadBatch {
  batch_id: string;
  total_items: number;
  items: UploadItem[];
  created_at?: string;
}

export interface CapturePage {
  id: string;
  page_index: number;
  rotation: number;
  crop_box?: {
    x: number;
    y: number;
    width: number;
    height: number;
  } | null;
  preview_url?: string;
  asset_id?: string;
}

export interface CaptureSession {
  id: string;
  status: 'draft' | 'finalizing' | 'completed' | 'abandoned';
  pages: CapturePage[];
  created_at: string;
  document_id?: string | null;
}

export interface ClassificationRule {
  id: string;
  name: string;
  pattern_type: 'keyword' | 'regex' | 'sender' | 'date_range';
  pattern_value: string;
  target_tag_id?: string | null;
  target_folder_id?: string | null;
  target_fields?: Record<string, any> | null;
  confidence: number;
  priority: number;
  is_active: boolean;
  created_at?: string;
}

export interface Schedule {
  id: string;
  name: string;
  task_type: string;
  cron_expression: string;
  is_active: boolean;
  next_run_at?: string | null;
  last_run_at?: string | null;
}

export interface UserSession {
  authenticated: boolean;
  username: string;
  theme?: 'light' | 'dark' | 'system';
}

export interface AuditEvent {
  id: string;
  action: string;
  details?: Record<string, any> | null;
  created_at: string;
}

import { Injectable, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { tap } from 'rxjs/operators';

export interface UserSettingsData {
  owner: string;
  preferences: Record<string, any>;
  pinned_tabs: string[];
}

export interface CapabilitiesData {
  max_upload_mb: number;
  max_batch_files: number;
  upload_concurrency: number;
  status_max_items: number;
  max_capture_pages: number;
  max_capture_total_mb: number;
  max_assembled_pdf_mb: number;
  heavy_job_concurrency: number;
  heavy_cpu_limit: number;
  heavy_memory_mb: number;
  supported_mimes: string[];
  available_ocr_languages: string[];
}

export interface ScheduleItem {
  id: string;
  owner: string;
  job_type: string;
  filter_config: Record<string, any>;
  mode: string;
  weekdays: number[];
  local_time: string;
  timezone: string;
  window_minutes: number;
  limits: Record<string, any>;
  is_active: boolean;
  next_run_at?: string | null;
  created_at: string;
}

@Injectable({
  providedIn: 'root'
})
export class SettingsService {
  private http = inject(HttpClient);

  settings = signal<UserSettingsData | null>(null);
  capabilities = signal<CapabilitiesData | null>(null);
  schedules = signal<ScheduleItem[]>([]);

  loadSettings(): Observable<UserSettingsData> {
    return this.http.get<UserSettingsData>('/api/v1/settings').pipe(
      tap(s => this.settings.set(s))
    );
  }

  updateSettings(data: { preferences?: Record<string, any>; pinned_tabs?: string[] }): Observable<UserSettingsData> {
    return this.http.patch<UserSettingsData>('/api/v1/settings', data).pipe(
      tap(s => this.settings.set(s))
    );
  }

  loadCapabilities(): Observable<CapabilitiesData> {
    return this.http.get<CapabilitiesData>('/api/v1/system/capabilities').pipe(
      tap(c => this.capabilities.set(c))
    );
  }

  loadSchedules(): Observable<ScheduleItem[]> {
    return this.http.get<ScheduleItem[]>('/api/v1/schedules').pipe(
      tap(s => this.schedules.set(s))
    );
  }

  createSchedule(data: {
    job_type: string;
    mode: string;
    weekdays: number[];
    local_time: string;
    timezone: string;
    filter_config?: Record<string, any>;
    window_minutes?: number;
    limits?: Record<string, any>;
  }): Observable<ScheduleItem> {
    return this.http.post<ScheduleItem>('/api/v1/schedules', data).pipe(
      tap(() => this.loadSchedules().subscribe())
    );
  }

  updateSchedule(id: string, data: Partial<ScheduleItem>): Observable<ScheduleItem> {
    return this.http.patch<ScheduleItem>(`/api/v1/schedules/${id}`, data).pipe(
      tap(() => this.loadSchedules().subscribe())
    );
  }

  deleteSchedule(id: string): Observable<any> {
    return this.http.delete(`/api/v1/schedules/${id}`).pipe(
      tap(() => this.loadSchedules().subscribe())
    );
  }

  runScheduleNow(id: string): Observable<any> {
    return this.http.post(`/api/v1/schedules/${id}/run-now`, {});
  }

  triggerExport(): Observable<{ export_id: string; status: string; message: string }> {
    return this.http.post<{ export_id: string; status: string; message: string }>('/api/v1/exports', {});
  }
}

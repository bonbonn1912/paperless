import { Injectable, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { tap } from 'rxjs/operators';

export interface CapturePageItem {
  id: string;
  session_id: string;
  asset_id?: string;
  page_number: number;
  rotation: number;
  crop_box?: { x: number; y: number; width: number; height: number } | null;
  upload_status: string;
  created_at: string;
  localDataUrl?: string;
}

export interface CaptureSessionData {
  id: string;
  owner: string;
  status: string;
  revision: number;
  expires_at: string;
  pages: CapturePageItem[];
  created_at: string;
  updated_at: string;
}

@Injectable({
  providedIn: 'root'
})
export class CaptureService {
  private http = inject(HttpClient);
  currentSession = signal<CaptureSessionData | null>(null);

  createSession(): Observable<CaptureSessionData> {
    return this.http.post<CaptureSessionData>('/api/v1/capture-sessions', {}).pipe(
      tap(s => this.currentSession.set(s))
    );
  }

  getSession(id: string): Observable<CaptureSessionData> {
    return this.http.get<CaptureSessionData>(`/api/v1/capture-sessions/${id}`).pipe(
      tap(s => this.currentSession.set(s))
    );
  }

  uploadPage(sessionId: string, pageId: string, blob: Blob, pageNumber: number, filename: string = 'capture.jpg'): Observable<CapturePageItem> {
    return this.http.put<CapturePageItem>(
      `/api/v1/capture-sessions/${sessionId}/pages/${pageId}/file?page_number=${pageNumber}&filename=${encodeURIComponent(filename)}`,
      blob,
      {
        headers: {
          'Content-Type': blob.type || 'image/jpeg'
        }
      }
    );
  }

  updateSession(sessionId: string, revision: number, pages: Array<{
    id: string;
    page_number: number;
    rotation?: number;
    crop_box?: any;
    deleted?: boolean;
  }>): Observable<CaptureSessionData> {
    return this.http.patch<CaptureSessionData>(`/api/v1/capture-sessions/${sessionId}`, {
      revision,
      pages
    }).pipe(
      tap(s => this.currentSession.set(s))
    );
  }

  finalizeSession(sessionId: string, orderedPageIds: string[], revision: number, title?: string): Observable<{ document_id: string; status: string; message: string }> {
    return this.http.post<{ document_id: string; status: string; message: string }>(`/api/v1/capture-sessions/${sessionId}/finalize`, {
      ordered_page_ids: orderedPageIds,
      draft_revision: revision,
      title: title || 'Scanned Document'
    }).pipe(
      tap(() => this.currentSession.set(null))
    );
  }

  discardSession(sessionId: string): Observable<any> {
    return this.http.delete(`/api/v1/capture-sessions/${sessionId}`).pipe(
      tap(() => this.currentSession.set(null))
    );
  }
}

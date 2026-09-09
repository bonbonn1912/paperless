import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { Document, DocumentSearchResult } from '../models';

export interface DocumentViewerManifest {
  document_id: string;
  mime_type: string;
  file_size: number;
  total_pages: number;
  pages: Array<{
    page_number: number;
    width: number;
    height: number;
    has_text: boolean;
    state?: string;
  }>;
  file_url: string;
  thumbnail_url: string;
  can_search: boolean;
}

export interface InDocSearchHit {
  page_number: number;
  snippet: string;
  bbox?: {
    x0: number;
    y0: number;
    x1: number;
    y1: number;
  };
}

export interface InDocSearchResult {
  document_id: string;
  query: string;
  total_hits: number;
  hits: InDocSearchHit[];
}

export interface DocumentPatchData {
  title?: string | null;
  sender?: string | null;
  document_date?: string | null;
  amount?: number | null;
  currency?: string | null;
  add_tag_ids?: string[];
  remove_tag_ids?: string[];
  add_folder_ids?: string[];
  remove_folder_ids?: string[];
  field_overrides?: Record<string, any>;
  resolve_review?: boolean;
}

@Injectable({
  providedIn: 'root'
})
export class DocumentService {
  private http = inject(HttpClient);

  list(params: {
    q?: string;
    folder_id?: string;
    tag_ids?: string[];
    tag_mode?: 'any' | 'all';
    classification_state?: string;
    processing_state?: string;
    date_from?: string;
    date_to?: string;
    limit?: number;
    offset?: number;
  } = {}): Observable<{ items: Document[]; total: number; limit: number; offset: number; snippets?: Record<string, string> }> {
    let httpParams = new HttpParams();
    if (params.q) httpParams = httpParams.set('q', params.q);
    if (params.folder_id) httpParams = httpParams.set('folder_id', params.folder_id);
    if (params.tag_ids && params.tag_ids.length > 0) {
      params.tag_ids.forEach(tid => {
        httpParams = httpParams.append('tag_ids', tid);
      });
    }
    if (params.tag_mode) httpParams = httpParams.set('tag_mode', params.tag_mode);
    if (params.classification_state) httpParams = httpParams.set('classification_state', params.classification_state);
    if (params.processing_state) httpParams = httpParams.set('processing_state', params.processing_state);
    if (params.date_from) httpParams = httpParams.set('date_from', params.date_from);
    if (params.date_to) httpParams = httpParams.set('date_to', params.date_to);
    if (params.limit) httpParams = httpParams.set('limit', params.limit.toString());
    if (params.offset) httpParams = httpParams.set('offset', params.offset.toString());

    return this.http.get<{ items: Document[]; total: number; limit: number; offset: number; snippets?: Record<string, string> }>('/api/v1/documents', {
      params: httpParams
    });
  }

  get(id: string): Observable<Document> {
    return this.http.get<Document>(`/api/v1/documents/${id}`);
  }

  patch(id: string, data: DocumentPatchData): Observable<Document> {
    return this.http.patch<Document>(`/api/v1/documents/${id}`, data);
  }

  delete(id: string): Observable<any> {
    return this.http.delete(`/api/v1/documents/${id}`);
  }

  getViewerManifest(id: string): Observable<DocumentViewerManifest> {
    return this.http.get<DocumentViewerManifest>(`/api/v1/documents/${id}/viewer-manifest`);
  }

  searchInDocument(id: string, q: string): Observable<InDocSearchResult> {
    return this.http.get<InDocSearchResult>(`/api/v1/documents/${id}/search`, {
      params: { q }
    });
  }

  getFileUrl(id: string): string {
    return `/api/v1/documents/${id}/file`;
  }

  getThumbnailUrl(id: string): string {
    return `/api/v1/documents/${id}/thumbnail`;
  }

  getPageFileUrl(id: string, pageNumber: number): string {
    return `/api/v1/documents/${id}/pages/${pageNumber}/file`;
  }
}

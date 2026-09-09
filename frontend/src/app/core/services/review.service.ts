import { Injectable, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { tap } from 'rxjs/operators';
import { Document } from '../models';

export interface ReviewConfirmPayload {
  tag_ids?: string[];
  excluded_tag_ids?: string[];
  field_overrides?: Record<string, any>;
  mark_as_reviewed?: boolean;
  create_rule?: boolean;
  rule_name?: string;
}

export interface BulkReviewPayload {
  document_ids: string[];
  add_tag_ids?: string[];
  remove_tag_ids?: string[];
  mark_as_reviewed?: boolean;
}

@Injectable({
  providedIn: 'root'
})
export class ReviewService {
  private http = inject(HttpClient);
  needsReviewCount = signal<number>(0);

  loadNeedsReviewCount(): Observable<{ total: number }> {
    return this.http.get<{ total: number }>('/api/v1/documents?classification_state=needs_review&limit=1').pipe(
      tap(res => this.needsReviewCount.set(res.total))
    );
  }

  getNeedsReviewDocs(limit: number = 20, offset: number = 0): Observable<{ items: Document[]; total: number }> {
    return this.http.get<{ items: Document[]; total: number }>(`/api/v1/documents?classification_state=needs_review&limit=${limit}&offset=${offset}`).pipe(
      tap(res => this.needsReviewCount.set(res.total))
    );
  }

  confirmReview(documentId: string, payload: ReviewConfirmPayload): Observable<any> {
    return this.http.post(`/api/v1/documents/${documentId}/review`, {
      tag_ids: payload.tag_ids || [],
      excluded_tag_ids: payload.excluded_tag_ids || [],
      field_overrides: payload.field_overrides || {},
      mark_as_reviewed: payload.mark_as_reviewed ?? true,
      create_rule: payload.create_rule ?? false,
      rule_name: payload.rule_name
    }).pipe(
      tap(() => this.loadNeedsReviewCount().subscribe())
    );
  }

  bulkReview(payload: BulkReviewPayload): Observable<any> {
    return this.http.post('/api/v1/documents/bulk-review', {
      document_ids: payload.document_ids,
      add_tag_ids: payload.add_tag_ids || [],
      remove_tag_ids: payload.remove_tag_ids || [],
      mark_as_reviewed: payload.mark_as_reviewed ?? true
    }).pipe(
      tap(() => this.loadNeedsReviewCount().subscribe())
    );
  }
}

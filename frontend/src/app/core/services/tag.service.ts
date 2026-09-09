import { Injectable, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, tap } from 'rxjs';
import { Tag } from '../models';

export interface TagResponse {
  id: string;
  owner: string;
  name: string;
  kind?: string;
  color: string;
  merged_into_id?: string | null;
  aliases: string[];
  document_count: number;
  created_at: string;
}

export interface TagResolveResponse {
  resolved_existing: boolean;
  tag_id: string;
  name: string;
  similar_tags: TagResponse[];
}

@Injectable({
  providedIn: 'root'
})
export class TagService {
  private http = inject(HttpClient);
  tags = signal<TagResponse[]>([]);

  loadTags(): Observable<TagResponse[]> {
    return this.http.get<TagResponse[]>('/api/v1/tags').pipe(
      tap((tags) => this.tags.set(tags))
    );
  }

  createOrResolve(name: string, color: string = '#6366f1', kind: string = 'user'): Observable<TagResolveResponse> {
    return this.http.post<TagResolveResponse>('/api/v1/tags', { name, color, kind }).pipe(
      tap(() => this.loadTags().subscribe())
    );
  }

  update(id: string, data: { name?: string; color?: string; kind?: string }): Observable<TagResponse> {
    return this.http.patch<TagResponse>(`/api/v1/tags/${id}`, data).pipe(
      tap(() => this.loadTags().subscribe())
    );
  }

  delete(id: string): Observable<{ message: string; affected_documents_count: number }> {
    return this.http.delete<{ message: string; affected_documents_count: number }>(`/api/v1/tags/${id}`).pipe(
      tap(() => this.loadTags().subscribe())
    );
  }

  addAlias(tagId: string, aliasName: string): Observable<any> {
    return this.http.post(`/api/v1/tags/${tagId}/aliases`, { name: aliasName }).pipe(
      tap(() => this.loadTags().subscribe())
    );
  }

  merge(sourceTagId: string, targetTagId: string): Observable<any> {
    return this.http.post(`/api/v1/tags/${sourceTagId}/merge`, { target_tag_id: targetTagId }).pipe(
      tap(() => this.loadTags().subscribe())
    );
  }

  assignToDocument(documentId: string, tagId: string): Observable<any> {
    return this.http.put(`/api/v1/documents/${documentId}/tags/${tagId}`, {});
  }

  removeFromDocument(documentId: string, tagId: string): Observable<any> {
    return this.http.delete(`/api/v1/documents/${documentId}/tags/${tagId}`);
  }
}

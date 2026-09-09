import { Injectable, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, tap } from 'rxjs';

export interface FolderNode {
  id: string;
  name: string;
  parent_id?: string | null;
  document_count: number;
  created_at: string;
  children?: FolderNode[];
}

@Injectable({
  providedIn: 'root'
})
export class FolderService {
  private http = inject(HttpClient);
  folders = signal<FolderNode[]>([]);
  folderTree = signal<FolderNode[]>([]);

  loadFolders(): Observable<FolderNode[]> {
    return this.http.get<FolderNode[]>('/api/v1/folders').pipe(
      tap((raw) => {
        this.folders.set(raw);
        this.folderTree.set(this.buildTree(raw));
      })
    );
  }

  create(name: string, parentId?: string | null): Observable<FolderNode> {
    return this.http.post<FolderNode>('/api/v1/folders', { name, parent_id: parentId || null }).pipe(
      tap(() => this.loadFolders().subscribe())
    );
  }

  update(id: string, name: string, parentId?: string | null): Observable<FolderNode> {
    return this.http.patch<FolderNode>(`/api/v1/folders/${id}`, { name, parent_id: parentId }).pipe(
      tap(() => this.loadFolders().subscribe())
    );
  }

  delete(id: string): Observable<{ message: string; deleted_count: number }> {
    return this.http.delete<{ message: string; deleted_count: number }>(`/api/v1/folders/${id}`).pipe(
      tap(() => this.loadFolders().subscribe())
    );
  }

  addDocumentToFolder(documentId: string, folderId: string): Observable<any> {
    return this.http.put(`/api/v1/documents/${documentId}/folders/${folderId}`, {});
  }

  removeDocumentFromFolder(documentId: string, folderId: string): Observable<any> {
    return this.http.delete(`/api/v1/documents/${documentId}/folders/${folderId}`);
  }

  private buildTree(nodes: FolderNode[]): FolderNode[] {
    const map = new Map<string, FolderNode>();
    const roots: FolderNode[] = [];

    nodes.forEach(node => {
      map.set(node.id, { ...node, children: [] });
    });

    nodes.forEach(node => {
      const current = map.get(node.id)!;
      if (node.parent_id && map.has(node.parent_id)) {
        map.get(node.parent_id)!.children!.push(current);
      } else {
        roots.push(current);
      }
    });

    return roots;
  }
}

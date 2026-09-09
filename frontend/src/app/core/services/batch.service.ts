import { Injectable, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { PollingService } from './polling.service';

export interface BatchItemMeta {
  client_item_id: string;
  original_name: string;
  file_size: number;
  mime_type: string;
  position: number;
}

export interface BatchCreateResponse {
  batch_id: string;
  total_items: number;
  max_batch_files: number;
  upload_concurrency: number;
  item_ids: Record<string, string>;
}

export interface UploadQueueItem {
  clientId: string;
  serverItemId?: string;
  file: File;
  name: string;
  size: number;
  status: 'pending' | 'uploading' | 'accepted' | 'processing' | 'ready' | 'failed' | 'duplicate';
  progress: number;
  error?: string;
  documentId?: string;
}

@Injectable({
  providedIn: 'root'
})
export class BatchService {
  private http = inject(HttpClient);
  private polling = inject(PollingService);

  queue = signal<UploadQueueItem[]>([]);
  isUploading = signal<boolean>(false);
  currentBatchId = signal<string | null>(null);

  addFiles(files: FileList | File[]) {
    const list = Array.from(files);
    const newItems: UploadQueueItem[] = list.map((file, idx) => ({
      clientId: `c_${Date.now()}_${idx}_${Math.random().toString(36).substring(2, 7)}`,
      file,
      name: file.name,
      size: file.size,
      status: 'pending',
      progress: 0,
    }));

    this.queue.update(q => [...q, ...newItems]);
  }

  clearQueue() {
    this.queue.set([]);
    this.currentBatchId.set(null);
    this.isUploading.set(false);
  }

  removeItem(clientId: string) {
    this.queue.update(q => q.filter(it => it.clientId !== clientId));
  }

  async startBatchUpload() {
    const items = this.queue().filter(i => i.status === 'pending' || i.status === 'failed');
    if (items.length === 0 || this.isUploading()) return;

    this.isUploading.set(true);

    // 1. Create Batch
    const payload = {
      items: items.map((it, idx) => ({
        client_item_id: it.clientId,
        original_name: it.name,
        file_size: it.size,
        mime_type: it.file.type || 'application/octet-stream',
        position: idx
      }))
    };

    try {
      const batchRes = await this.http.post<BatchCreateResponse>('/api/v1/upload-batches', payload).toPromise();
      if (!batchRes) throw new Error('Failed to create upload batch');

      const batchId = batchRes.batch_id;
      this.currentBatchId.set(batchId);
      this.polling.watchBatch(batchId);

      // Map server item IDs to queue
      this.queue.update(q => q.map(it => {
        if (batchRes.item_ids[it.clientId]) {
          return { ...it, serverItemId: batchRes.item_ids[it.clientId] };
        }
        return it;
      }));

      // 2. Upload files in parallel with upload_concurrency (default 2)
      const concurrency = batchRes.upload_concurrency || 2;
      const queueToProcess = [...items];
      
      const uploadWorker = async () => {
        while (queueToProcess.length > 0) {
          const item = queueToProcess.shift();
          if (!item) break;

          const serverItemId = batchRes.item_ids[item.clientId];
          if (!serverItemId) continue;

          this.updateItemStatus(item.clientId, 'uploading', 20);

          try {
            const resp: any = await this.http.put(
              `/api/v1/upload-batches/${batchId}/items/${serverItemId}/file`,
              item.file,
              {
                headers: {
                  'Content-Type': item.file.type || 'application/octet-stream',
                  'Idempotency-Key': `${batchId}_${serverItemId}`
                }
              }
            ).toPromise();

            if (resp && resp.is_duplicate) {
              this.updateItemStatus(item.clientId, 'duplicate', 100, undefined, resp.document_id);
            } else {
              this.updateItemStatus(item.clientId, 'accepted', 100, undefined, resp?.document_id);
            }
          } catch (err: any) {
            this.updateItemStatus(item.clientId, 'failed', 0, err.error?.detail || err.message || 'Upload error');
          }
        }
      };

      const workers = Array.from({ length: Math.min(concurrency, items.length) }, () => uploadWorker());
      await Promise.all(workers);

    } catch (err: any) {
      console.error('Batch upload error:', err);
    } finally {
      this.isUploading.set(false);
    }
  }

  private updateItemStatus(clientId: string, status: UploadQueueItem['status'], progress: number, error?: string, docId?: string) {
    this.queue.update(q => q.map(it => {
      if (it.clientId === clientId) {
        return {
          ...it,
          status,
          progress,
          error: error ?? it.error,
          documentId: docId ?? it.documentId
        };
      }
      return it;
    }));
  }
}

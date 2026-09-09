import { Injectable, inject, signal, OnDestroy } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Subject, Subscription, timer } from 'rxjs';
import { switchMap, tap, filter } from 'rxjs/operators';
import { AuthService } from './auth.service';

export interface JobSummary {
  id: string;
  state: 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled' | 'cancelling';
  step?: string | null;
  processed_pages: number;
  total_pages: number;
  attempt: number;
  updated_at: string;
  next_run_at?: string | null;
  error_code?: string | null;
}

export interface StatusItemSummary {
  batch_id?: string | null;
  item_id?: string | null;
  document_id?: string | null;
  upload_state: string;
  processing_state?: string | null;
  classification_state?: string | null;
  index_state?: string | null;
  review_reasons: string[];
  retryable: boolean;
  job?: JobSummary | null;
}

export interface BatchStatusSummary {
  batch_id: string;
  total: number;
  uploaded: number;
  upload_failed: number;
  waiting_for_upload: number;
  ready: number;
  needs_review: number;
  processing: number;
  queued: number;
  failed: number;
  cancelled: number;
  terminal: boolean;
}

export interface StatusPollResponse {
  revision: string;
  unchanged: boolean;
  batches: BatchStatusSummary[];
  items: StatusItemSummary[];
  poll_after_ms: number;
}

@Injectable({
  providedIn: 'root'
})
export class PollingService implements OnDestroy {
  private http = inject(HttpClient);
  private authService = inject(AuthService);

  private watchedBatchIds = new Set<string>();
  private watchedDocIds = new Set<string>();
  private knownRevision: string | null = null;
  private pollSub?: Subscription;

  // Reactive state
  activeBatchSummaries = signal<BatchStatusSummary[]>([]);
  activeItems = signal<StatusItemSummary[]>([]);
  totalActiveJobs = signal<number>(0);
  isPolling = signal<boolean>(false);

  // Status updates stream
  statusUpdates$ = new Subject<StatusPollResponse>();

  constructor() {
    this.startPolling();
  }

  watchBatch(batchId: string) {
    this.watchedBatchIds.add(batchId);
  }

  unwatchBatch(batchId: string) {
    this.watchedBatchIds.delete(batchId);
  }

  watchDocument(docId: string) {
    this.watchedDocIds.add(docId);
  }

  unwatchDocument(docId: string) {
    this.watchedDocIds.delete(docId);
  }

  startPolling() {
    if (this.pollSub) return;

    this.pollSub = timer(0, 2000).pipe(
      filter(() => this.authService.isAuthenticated()),
      filter(() => this.watchedBatchIds.size > 0 || this.watchedDocIds.size > 0),
      switchMap(() => {
        this.isPolling.set(true);
        const payload = {
          batch_ids: Array.from(this.watchedBatchIds).slice(0, 10),
          document_ids: Array.from(this.watchedDocIds).slice(0, 20),
          known_revision: this.knownRevision,
        };
        return this.http.post<StatusPollResponse>('/api/v1/processing/status', payload);
      }),
      tap({
        next: (resp) => {
          this.isPolling.set(false);
          this.knownRevision = resp.revision;
          if (!resp.unchanged) {
            this.activeBatchSummaries.set(resp.batches);
            this.activeItems.set(resp.items);

            let activeCount = 0;
            resp.items.forEach(it => {
              if (it.job && (it.job.state === 'running' || it.job.state === 'queued')) {
                activeCount++;
              }
            });
            this.totalActiveJobs.set(activeCount);
            this.statusUpdates$.next(resp);

            // Automatically prune finished batches
            resp.batches.forEach(b => {
              if (b.terminal) {
                this.unwatchBatch(b.batch_id);
              }
            });
          }
        },
        error: () => {
          this.isPolling.set(false);
        }
      })
    ).subscribe();
  }

  stopPolling() {
    if (this.pollSub) {
      this.pollSub.unsubscribe();
      this.pollSub = undefined;
    }
  }

  ngOnDestroy() {
    this.stopPolling();
  }
}

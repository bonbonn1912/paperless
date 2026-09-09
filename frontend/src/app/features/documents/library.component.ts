import { Component, inject, signal, OnInit, DestroyRef, computed, HostListener } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Subscription, firstValueFrom } from 'rxjs';
import { DialogDirective } from '../../shared/directives/dialog.directive';
import { CommonModule } from '@angular/common';
import { RouterModule, ActivatedRoute, Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { DocumentService } from '../../core/services/document.service';
import { TagService, TagResponse } from '../../core/services/tag.service';
import { FolderService, FolderNode } from '../../core/services/folder.service';
import { PollingService } from '../../core/services/polling.service';
import { Document } from '../../core/models';
import { IconComponent } from '../../shared/components/icon/icon.component';

@Component({
  selector: 'app-library',
  standalone: true,
  imports: [CommonModule, RouterModule, FormsModule, IconComponent, DialogDirective],
  templateUrl: './library.component.html'
})
export class LibraryComponent implements OnInit {
  docService = inject(DocumentService);
  tagService = inject(TagService);
  folderService = inject(FolderService);
  polling = inject(PollingService);
  route = inject(ActivatedRoute);
  router = inject(Router);

  documents = signal<Document[]>([]);
  total = signal<number>(0);
  loading = signal<boolean>(false);
  viewMode = signal<'grid' | 'list'>('grid');
  activeFilterTab = signal<string | null>(null);
  tagsDropdownOpen = signal<boolean>(false);

  Math = Math;
  readonly pageSize = 48;
  offset = signal(0);
  searchQuery = '';
  errorMessage = signal<string | null>(null);
  showDelete = signal(false);
  deleting = signal(false);
  private tagId = signal<string | null>(null);
  private folderId = signal<string | null>(null);
  selectedTag = computed(() => this.tagService.tags().find(t => t.id === this.tagId()) || null);
  selectedFolder = computed(() => this.folderService.folders().find(f => f.id === this.folderId()) || null);
  selectedDocIds = new Set<string>();
  private destroyRef = inject(DestroyRef);
  private request?: Subscription;

  ngOnInit() {
    this.route.queryParams.pipe(takeUntilDestroyed(this.destroyRef)).subscribe(params => {
      this.tagId.set(params['tag'] || null);
      this.folderId.set(params['folder'] || null);
      this.activeFilterTab.set(params['state'] || null);
      this.searchQuery = params['q'] || '';
      this.offset.set(0); this.selectedDocIds.clear();
      this.loadDocuments();
    });
    this.destroyRef.onDestroy(() => this.request?.unsubscribe());
  }

  loadDocuments() {
    this.request?.unsubscribe();
    this.loading.set(true); this.errorMessage.set(null);
    this.request = this.docService.list({
      q: this.searchQuery || undefined,
      tag_ids: this.tagId() ? [this.tagId()!] : undefined,
      folder_id: this.folderId() || undefined,
      classification_state: this.activeFilterTab() === 'needs_review' ? 'needs_review' : undefined,
      limit: this.pageSize, offset: this.offset()
    }).subscribe({
      next: res => { this.documents.set(res.items); this.total.set(res.total); this.loading.set(false); },
      error: () => { this.loading.set(false); this.errorMessage.set('Deine Dokumente konnten nicht geladen werden.'); }
    });
  }
  @HostListener('document:click', ['$event'])
  onDocumentClick(event: MouseEvent) {
    const target = event.target as HTMLElement;
    if (!target.closest('.tags-filter-dropdown')) {
      this.tagsDropdownOpen.set(false);
    }
  }

  selectTagFilter(t: TagResponse) {
    this.tagsDropdownOpen.set(false);
    this.router.navigate(['/documents'], {
      queryParams: { tag: this.tagId() === t.id ? null : t.id },
      queryParamsHandling: 'merge'
    });
  }

  clearTagFilter(event?: Event) {
    if (event) event.stopPropagation();
    this.tagsDropdownOpen.set(false);
    this.router.navigate(['/documents'], {
      queryParams: { tag: null },
      queryParamsHandling: 'merge'
    });
  }

  submitSearch() { this.router.navigate(['/documents'], { queryParams: { q: this.searchQuery.trim() || null }, queryParamsHandling: 'merge' }); }
  setFilterTab(tab: string) { this.router.navigate(['/documents'], { queryParams: { state: this.activeFilterTab() === tab ? null : tab }, queryParamsHandling: 'merge' }); }
  toggleTagFilter(t: TagResponse) { this.router.navigate(['/documents'], { queryParams: { tag: this.tagId() === t.id ? null : t.id }, queryParamsHandling: 'merge' }); }
  clearFilters() { this.router.navigate(['/documents']); }
  hasFilters() { return !!(this.tagId() || this.folderId() || this.activeFilterTab() || this.searchQuery); }
  changePage(direction: number) { this.offset.update(value => Math.max(0,value + direction * this.pageSize)); this.selectedDocIds.clear(); this.loadDocuments(); }
  trackDoc(_index: number, doc: Document) { return doc.id; }
  formatAmount(doc: Document) {
    if (doc.amount_decimal == null) return '–';
    try { return new Intl.NumberFormat('de-DE', { style:'currency', currency: doc.currency || 'EUR' }).format(Number(doc.amount_decimal)); }
    catch { return doc.amount_decimal + ' ' + (doc.currency || 'EUR'); }
  }

  toggleDocSelect(id: string) {
    if (this.selectedDocIds.has(id)) {
      this.selectedDocIds.delete(id);
    } else {
      this.selectedDocIds.add(id);
    }
  }

  toggleSelectAll() {
    if (this.selectedDocIds.size === this.documents().length) {
      this.selectedDocIds.clear();
    } else {
      this.documents().forEach(d => this.selectedDocIds.add(d.id));
    }
  }

  async bulkDelete() {
    if (this.deleting()) return;
    this.deleting.set(true);
    const results = await Promise.allSettled(Array.from(this.selectedDocIds).map(id => firstValueFrom(this.docService.delete(id)).then(() => this.selectedDocIds.delete(id))));
    this.deleting.set(false); this.showDelete.set(false); this.loadDocuments();
    if (results.some(r => r.status === 'rejected')) this.errorMessage.set('Einige Dokumente konnten nicht gelöscht werden. Bitte erneut versuchen.');
  }

  onThumbError(event: any) {
    event.target.style.display = 'none';
  }
}

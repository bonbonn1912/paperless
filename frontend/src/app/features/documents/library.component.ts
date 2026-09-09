import { Component, inject, signal, OnInit } from '@angular/core';
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
  imports: [CommonModule, RouterModule, FormsModule, IconComponent],
  template: `
    <div class="space-y-6">
      <!-- Top Action Bar & Filter Chips -->
      <div class="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 class="text-2xl font-bold tracking-tight">Dokumente</h1>
          <p class="text-xs text-slate-500 mt-0.5">
            {{ total() }} {{ total() === 1 ? 'Dokument gefunden' : 'Dokumente gefunden' }}
            <span *ngIf="selectedTag()">· Gefiltert nach Tag: <strong class="text-indigo-600">{{ selectedTag()?.name }}</strong></span>
            <span *ngIf="selectedFolder()">· Im Ordner: <strong class="text-indigo-600">{{ selectedFolder()?.name }}</strong></span>
          </p>
        </div>

        <div class="flex items-center gap-2 flex-wrap">
          <!-- View Toggle -->
          <div class="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-0.5 flex items-center shadow-xs">
            <button
              type="button"
              (click)="viewMode.set('grid')"
              [class.bg-slate-100]="viewMode() === 'grid'"
              [class.dark:bg-slate-700]="viewMode() === 'grid'"
              class="p-2 rounded-lg text-slate-600 dark:text-slate-300 touch-target flex items-center justify-center transition"
              title="Kachelansicht"
            >
              <app-icon name="grid" [size]="16"></app-icon>
            </button>
            <button
              type="button"
              (click)="viewMode.set('list')"
              [class.bg-slate-100]="viewMode() === 'list'"
              [class.dark:bg-slate-700]="viewMode() === 'list'"
              class="p-2 rounded-lg text-slate-600 dark:text-slate-300 touch-target flex items-center justify-center transition"
              title="Listenansicht"
            >
              <app-icon name="list" [size]="16"></app-icon>
            </button>
          </div>

          <!-- Quick Actions -->
          <a
            routerLink="/batch-upload"
            class="px-3.5 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-xs font-semibold flex items-center gap-2 touch-target shadow-xs transition"
          >
            <app-icon name="plus" [size]="16"></app-icon>
            <span>Dokumente hinzufügen</span>
          </a>
        </div>
      </div>

      <!-- Filter Tabs / Pills -->
      <div class="flex items-center gap-2 overflow-x-auto pb-1 text-xs">
        <button
          type="button"
          (click)="clearFilters()"
          [class.bg-indigo-600]="!activeFilterTab() && !selectedTag() && !selectedFolder()"
          [class.text-white]="!activeFilterTab() && !selectedTag() && !selectedFolder()"
          [class.bg-white]="activeFilterTab() || selectedTag() || selectedFolder()"
          [class.dark:bg-slate-800]="activeFilterTab() || selectedTag() || selectedFolder()"
          class="px-3 py-1.5 rounded-xl border border-slate-200 dark:border-slate-700 font-medium touch-target transition whitespace-nowrap shadow-xs"
        >
          Alle
        </button>

        <button
          type="button"
          (click)="setFilterTab('needs_review')"
          [class.bg-amber-500]="activeFilterTab() === 'needs_review'"
          [class.text-white]="activeFilterTab() === 'needs_review'"
          [class.bg-white]="activeFilterTab() !== 'needs_review'"
          [class.dark:bg-slate-800]="activeFilterTab() !== 'needs_review'"
          class="px-3 py-1.5 rounded-xl border border-slate-200 dark:border-slate-700 font-medium touch-target transition whitespace-nowrap shadow-xs flex items-center gap-1.5"
        >
          <app-icon name="alert-triangle" [size]="14"></app-icon>
          <span>Zu prüfen</span>
        </button>

        <!-- Pinned Tag Pills -->
        <button
          *ngFor="let t of tagService.tags()"
          type="button"
          (click)="toggleTagFilter(t)"
          [style.borderColor]="selectedTag()?.id === t.id ? t.color : ''"
          [style.backgroundColor]="selectedTag()?.id === t.id ? t.color + '22' : ''"
          [style.color]="selectedTag()?.id === t.id ? t.color : ''"
          class="px-3 py-1.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 font-medium touch-target transition whitespace-nowrap shadow-xs flex items-center gap-1.5"
        >
          <span class="w-2 h-2 rounded-full" [style.backgroundColor]="t.color"></span>
          <span>{{ t.name }}</span>
        </button>
      </div>

      <!-- Bulk Selection Actions Bar (when items selected) -->
      <div *ngIf="selectedDocIds.size > 0" class="p-3 bg-indigo-50 dark:bg-indigo-950/60 border border-indigo-200 dark:border-indigo-800 rounded-2xl flex items-center justify-between flex-wrap gap-3">
        <span class="text-xs font-semibold text-indigo-900 dark:text-indigo-200">
          {{ selectedDocIds.size }} Dokumente ausgewählt
        </span>
        <div class="flex items-center gap-2">
          <button
            type="button"
            (click)="bulkDelete()"
            class="px-3 py-1.5 bg-rose-600 hover:bg-rose-700 text-white rounded-xl text-xs font-medium touch-target flex items-center gap-1.5 transition"
          >
            <app-icon name="trash" [size]="14"></app-icon>
            <span>Löschen</span>
          </button>
          <button
            type="button"
            (click)="selectedDocIds.clear()"
            class="px-3 py-1.5 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl text-xs font-medium touch-target transition"
          >
            Auswahl aufheben
          </button>
        </div>
      </div>

      <!-- Documents Grid View -->
      <div *ngIf="viewMode() === 'grid' && !loading()" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        <div
          *ngFor="let doc of documents()"
          class="group relative bg-white dark:bg-slate-850 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-xs hover:shadow-md transition overflow-hidden flex flex-col"
        >
          <!-- Checkbox overlay -->
          <div class="absolute top-2.5 left-2.5 z-10">
            <input
              type="checkbox"
              [checked]="selectedDocIds.has(doc.id)"
              (change)="toggleDocSelect(doc.id)"
              class="w-4 h-4 rounded text-indigo-600 bg-white/90 border-slate-300 focus:ring-indigo-500 cursor-pointer"
            />
          </div>

          <!-- Thumbnail Link -->
          <a [routerLink]="['/documents', doc.id]" class="relative aspect-4/3 bg-slate-100 dark:bg-slate-800 overflow-hidden flex items-center justify-center cursor-pointer">
            <img
              [src]="docService.getThumbnailUrl(doc.id)"
              [alt]="doc.title || doc.original_name"
              loading="lazy"
              (error)="onThumbError($event)"
              class="w-full h-full object-cover object-top group-hover:scale-105 transition duration-300"
            />
            
            <!-- Needs Review Badge -->
            <div
              *ngIf="doc.classification_state === 'needs_review'"
              class="absolute top-2.5 right-2.5 px-2 py-0.5 bg-amber-500 text-white rounded-full text-[10px] font-bold tracking-wide uppercase flex items-center gap-1 shadow-sm"
            >
              <app-icon name="alert-triangle" [size]="12"></app-icon>
              <span>Zu prüfen</span>
            </div>

            <!-- Processing badge -->
            <div
              *ngIf="doc.processing_state === 'processing' || doc.processing_state === 'queued'"
              class="absolute bottom-2.5 right-2.5 px-2 py-0.5 bg-indigo-600 text-white rounded-full text-[10px] font-bold flex items-center gap-1 shadow-sm"
            >
              <app-icon name="refresh-cw" [size]="12" extraClass="animate-spin"></app-icon>
              <span>OCR läuft</span>
            </div>
          </a>

          <!-- Details Card Footer -->
          <div class="p-3.5 flex-1 flex flex-col justify-between space-y-2.5">
            <div>
              <a [routerLink]="['/documents', doc.id]" class="font-semibold text-sm hover:text-indigo-600 dark:hover:text-indigo-400 line-clamp-1">
                {{ doc.title || doc.original_name }}
              </a>
              <p *ngIf="doc.sender" class="text-xs text-slate-500 line-clamp-1 mt-0.5">
                {{ doc.sender }}
              </p>
            </div>

            <!-- Tags -->
            <div class="flex items-center gap-1.5 flex-wrap">
              <span
                *ngFor="let t of doc.tags"
                class="px-2 py-0.5 text-[11px] font-medium rounded-md"
                [style.backgroundColor]="t.color + '20'"
                [style.color]="t.color"
              >
                {{ t.name }}
              </span>
            </div>

            <!-- Meta: Date & Amount -->
            <div class="flex items-center justify-between text-xs text-slate-400 pt-2 border-t border-slate-100 dark:border-slate-800">
              <span>{{ doc.document_date || (doc.created_at | date:'dd.MM.yyyy') }}</span>
              <span *ngIf="doc.amount_decimal" class="font-semibold text-slate-700 dark:text-slate-200">
                {{ doc.amount_decimal }} {{ doc.currency || '€' }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- Documents List / Table View -->
      <div *ngIf="viewMode() === 'list' && !loading()" class="bg-white dark:bg-slate-850 rounded-2xl border border-slate-200 dark:border-slate-800 overflow-hidden shadow-xs">
        <table class="w-full text-left text-xs">
          <thead class="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800 font-semibold text-slate-500 uppercase tracking-wider">
            <tr>
              <th class="p-3.5 w-10">
                <input
                  type="checkbox"
                  (change)="toggleSelectAll()"
                  class="w-4 h-4 rounded text-indigo-600 cursor-pointer"
                />
              </th>
              <th class="p-3.5">Dokument</th>
              <th class="p-3.5 hidden sm:table-cell">Absender</th>
              <th class="p-3.5">Tags</th>
              <th class="p-3.5 hidden md:table-cell">Datum</th>
              <th class="p-3.5 text-right">Betrag</th>
              <th class="p-3.5 text-right">Aktion</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100 dark:divide-slate-800">
            <tr *ngFor="let doc of documents()" class="hover:bg-slate-50/70 dark:hover:bg-slate-800/40 transition">
              <td class="p-3.5">
                <input
                  type="checkbox"
                  [checked]="selectedDocIds.has(doc.id)"
                  (change)="toggleDocSelect(doc.id)"
                  class="w-4 h-4 rounded text-indigo-600 cursor-pointer"
                />
              </td>
              <td class="p-3.5">
                <a [routerLink]="['/documents', doc.id]" class="font-semibold text-sm hover:text-indigo-600 dark:hover:text-indigo-400 block truncate max-w-xs">
                  {{ doc.title || doc.original_name }}
                </a>
                <span *ngIf="doc.classification_state === 'needs_review'" class="inline-flex items-center gap-1 text-[10px] text-amber-600 font-bold">
                  <app-icon name="alert-triangle" [size]="10"></app-icon>
                  Zu prüfen
                </span>
              </td>
              <td class="p-3.5 hidden sm:table-cell text-slate-600 dark:text-slate-300">
                {{ doc.sender || '-' }}
              </td>
              <td class="p-3.5">
                <div class="flex items-center gap-1 flex-wrap">
                  <span
                    *ngFor="let t of doc.tags"
                    class="px-1.5 py-0.5 text-[10px] font-medium rounded"
                    [style.backgroundColor]="t.color + '20'"
                    [style.color]="t.color"
                  >
                    {{ t.name }}
                  </span>
                </div>
              </td>
              <td class="p-3.5 hidden md:table-cell text-slate-500">
                {{ doc.document_date || (doc.created_at | date:'dd.MM.yyyy') }}
              </td>
              <td class="p-3.5 text-right font-medium text-slate-700 dark:text-slate-200">
                {{ doc.amount_decimal ? (doc.amount_decimal + ' ' + (doc.currency || '€')) : '-' }}
              </td>
              <td class="p-3.5 text-right">
                <a
                  [routerLink]="['/documents', doc.id]"
                  class="p-1.5 rounded-lg text-slate-500 hover:text-indigo-600 hover:bg-slate-100 dark:hover:bg-slate-800 touch-target inline-flex items-center justify-center"
                >
                  <app-icon name="eye" [size]="16"></app-icon>
                </a>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Empty State -->
      <div *ngIf="!loading() && documents().length === 0" class="p-12 text-center bg-white dark:bg-slate-850 rounded-3xl border border-slate-200 dark:border-slate-800 space-y-4">
        <div class="inline-flex p-4 bg-slate-100 dark:bg-slate-800 rounded-full text-slate-400">
          <app-icon name="file-text" [size]="36"></app-icon>
        </div>
        <div class="space-y-1">
          <h3 class="font-bold text-base">Keine Dokumente gefunden</h3>
          <p class="text-xs text-slate-500 max-w-sm mx-auto">
            Laden Sie Dokumente per Drag & Drop hoch oder scannen Sie Belege mit der Smartphone-Kamera.
          </p>
        </div>
        <div class="flex items-center justify-center gap-3 pt-2">
          <a
            routerLink="/batch-upload"
            class="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold rounded-xl touch-target transition shadow-xs"
          >
            Dokument hochladen
          </a>
        </div>
      </div>
    </div>
  `
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

  selectedTag = signal<TagResponse | null>(null);
  selectedFolder = signal<FolderNode | null>(null);
  selectedDocIds = new Set<string>();

  ngOnInit() {
    this.route.queryParams.subscribe(params => {
      if (params['tag']) {
        const found = this.tagService.tags().find(t => t.id === params['tag']);
        this.selectedTag.set(found || null);
      } else {
        this.selectedTag.set(null);
      }

      if (params['folder']) {
        const found = this.folderService.folders().find(f => f.id === params['folder']);
        this.selectedFolder.set(found || null);
      } else {
        this.selectedFolder.set(null);
      }

      this.loadDocuments(params['q']);
    });
  }

  loadDocuments(q?: string) {
    this.loading.set(true);
    const tagIds = this.selectedTag() ? [this.selectedTag()!.id] : undefined;
    const folderId = this.selectedFolder() ? this.selectedFolder()!.id : undefined;
    const classificationState = this.activeFilterTab() === 'needs_review' ? 'needs_review' : undefined;

    this.docService.list({
      q,
      tag_ids: tagIds,
      folder_id: folderId,
      classification_state: classificationState,
      limit: 50
    }).subscribe({
      next: (res) => {
        this.documents.set(res.items);
        this.total.set(res.total);
        this.loading.set(false);
      },
      error: () => this.loading.set(false)
    });
  }

  setFilterTab(tab: string) {
    this.activeFilterTab.set(tab);
    this.loadDocuments();
  }

  toggleTagFilter(t: TagResponse) {
    if (this.selectedTag()?.id === t.id) {
      this.selectedTag.set(null);
      this.router.navigate(['/documents'], { queryParams: { tag: null }, queryParamsHandling: 'merge' });
    } else {
      this.selectedTag.set(t);
      this.router.navigate(['/documents'], { queryParams: { tag: t.id }, queryParamsHandling: 'merge' });
    }
  }

  clearFilters() {
    this.activeFilterTab.set(null);
    this.selectedTag.set(null);
    this.selectedFolder.set(null);
    this.router.navigate(['/documents']);
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

  bulkDelete() {
    if (!confirm(`${this.selectedDocIds.size} Dokumente wirklich löschen?`)) return;
    const promises = Array.from(this.selectedDocIds).map(id => this.docService.delete(id).toPromise());
    Promise.all(promises).then(() => {
      this.selectedDocIds.clear();
      this.loadDocuments();
    });
  }

  onThumbError(event: any) {
    event.target.style.display = 'none';
  }
}

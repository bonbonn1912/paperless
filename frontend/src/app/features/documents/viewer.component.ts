import { Component, inject, signal, OnInit, ElementRef, ViewChild, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule, ActivatedRoute, Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import * as pdfjsLib from 'pdfjs-dist';
import { DocumentService, DocumentViewerManifest, InDocSearchHit } from '../../core/services/document.service';
import { TagService, TagResponse } from '../../core/services/tag.service';
import { FolderService, FolderNode } from '../../core/services/folder.service';
import { Document } from '../../core/models';
import { IconComponent } from '../../shared/components/icon/icon.component';

@Component({
  selector: 'app-document-viewer',
  standalone: true,
  imports: [CommonModule, RouterModule, FormsModule, IconComponent],
  template: `
    <div class="h-[calc(100vh-6rem)] flex flex-col -m-4 sm:-m-6 bg-slate-100 dark:bg-slate-900 overflow-hidden">
      <!-- Viewer Top Toolbar -->
      <div class="h-14 bg-white dark:bg-slate-850 border-b border-slate-200 dark:border-slate-800 px-4 flex items-center justify-between shrink-0 z-20 shadow-xs">
        <!-- Back and Title -->
        <div class="flex items-center gap-3 min-w-0">
          <a
            routerLink="/documents"
            class="p-2 rounded-xl text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 touch-target flex items-center justify-center shrink-0"
            title="Zurück zur Übersicht"
          >
            <app-icon name="chevron-left" [size]="20"></app-icon>
          </a>

          <div class="min-w-0">
            <h2 class="text-sm font-bold truncate text-slate-800 dark:text-slate-100">
              {{ doc()?.title || doc()?.original_name }}
            </h2>
            <p class="text-[11px] text-slate-400 truncate">
              {{ doc()?.mime_type }} · {{ formatSize(doc()?.file_size || 0) }}
            </p>
          </div>
        </div>

        <!-- Canvas Controls -->
        <div class="flex items-center gap-1 sm:gap-2">
          <!-- Page Nav -->
          <div *ngIf="totalPages() > 1" class="flex items-center gap-1 bg-slate-100 dark:bg-slate-800 rounded-xl px-2 py-1 text-xs font-semibold">
            <button
              type="button"
              (click)="prevPage()"
              [disabled]="currentPage() <= 1"
              class="p-1 rounded hover:bg-slate-200 dark:hover:bg-slate-700 disabled:opacity-30 touch-target flex items-center justify-center"
            >
              <app-icon name="chevron-left" [size]="14"></app-icon>
            </button>
            <span class="px-1">{{ currentPage() }} / {{ totalPages() }}</span>
            <button
              type="button"
              (click)="nextPage()"
              [disabled]="currentPage() >= totalPages()"
              class="p-1 rounded hover:bg-slate-200 dark:hover:bg-slate-700 disabled:opacity-30 touch-target flex items-center justify-center"
            >
              <app-icon name="chevron-right" [size]="14"></app-icon>
            </button>
          </div>

          <!-- Zoom & Rotate -->
          <div class="hidden sm:flex items-center gap-1 bg-slate-100 dark:bg-slate-800 rounded-xl p-1 text-xs">
            <button
              type="button"
              (click)="zoomOut()"
              class="p-1.5 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-700 touch-target flex items-center justify-center"
              title="Verkleinern"
            >
              <app-icon name="zoom-out" [size]="16"></app-icon>
            </button>
            <span class="px-1 text-[11px] font-mono">{{ Math.round(zoom() * 100) }}%</span>
            <button
              type="button"
              (click)="zoomIn()"
              class="p-1.5 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-700 touch-target flex items-center justify-center"
              title="Vergrößern"
            >
              <app-icon name="zoom-in" [size]="16"></app-icon>
            </button>
            <button
              type="button"
              (click)="rotate()"
              class="p-1.5 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-700 touch-target flex items-center justify-center ml-1 border-l border-slate-200 dark:border-slate-700"
              title="90° Drehen"
            >
              <app-icon name="rotate-cw" [size]="16"></app-icon>
            </button>
          </div>

          <!-- In-Doc Search Input -->
          <div class="relative hidden md:block">
            <input
              type="search"
              [(ngModel)]="searchInDocQuery"
              (keydown.enter)="onSearchInDoc()"
              placeholder="Im Dokument suchen..."
              class="w-44 pl-8 pr-3 py-1.5 text-xs bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl focus:outline-hidden focus:border-indigo-500"
            />
            <div class="absolute inset-y-0 left-0 pl-2.5 flex items-center pointer-events-none text-slate-400">
              <app-icon name="search" [size]="14"></app-icon>
            </div>
          </div>

          <!-- Download Button -->
          <a
            [href]="docService.getFileUrl(docId)"
            download
            class="p-2 rounded-xl text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 touch-target flex items-center justify-center"
            title="Originaldatei herunterladen"
          >
            <app-icon name="download" [size]="18"></app-icon>
          </a>

          <!-- Toggle Sidebar (Mobile) -->
          <button
            type="button"
            (click)="metaOpen.set(!metaOpen())"
            [class.text-indigo-600]="metaOpen()"
            class="p-2 rounded-xl text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 touch-target flex items-center justify-center lg:hidden"
            title="Metadaten ein-/ausblenden"
          >
            <app-icon name="edit" [size]="18"></app-icon>
          </button>
        </div>
      </div>

      <!-- Main Viewer Area (Split: Thumbnails Tray + Canvas Area + Metadata Sidebar) -->
      <div class="flex-1 flex overflow-hidden relative">
        <!-- Thumbnail Tray (Desktop) -->
        <div *ngIf="manifest() && manifest()!.total_pages > 1" class="hidden md:flex flex-col w-28 bg-white dark:bg-slate-850 border-r border-slate-200 dark:border-slate-800 p-2 overflow-y-auto space-y-2 shrink-0">
          <button
            *ngFor="let p of manifest()!.pages; let idx = index"
            type="button"
            (click)="goToPage(idx + 1)"
            [class.ring-2]="currentPage() === idx + 1"
            [class.ring-indigo-600]="currentPage() === idx + 1"
            class="relative rounded-lg overflow-hidden border border-slate-200 dark:border-slate-700 aspect-3/4 bg-slate-50 dark:bg-slate-800 p-1 flex flex-col items-center justify-center group touch-target transition"
          >
            <img
              [src]="docService.getPageFileUrl(docId, idx + 1)"
              [alt]="'Seite ' + (idx + 1)"
              class="w-full h-full object-contain"
              (error)="onThumbError($event)"
            />
            <span class="absolute bottom-1 bg-black/60 text-white text-[10px] px-1.5 py-0.5 rounded font-mono">
              {{ idx + 1 }}
            </span>
          </button>
        </div>

        <!-- Center Canvas / Image Container -->
        <div #viewportContainer class="flex-1 overflow-auto flex items-center justify-center p-4 relative select-none">
          <!-- In-Doc Search Hits Indicator -->
          <div *ngIf="searchHits().length > 0" class="absolute top-4 left-4 z-10 bg-white/90 dark:bg-slate-850/90 backdrop-blur border border-indigo-200 dark:border-indigo-800 px-3 py-1.5 rounded-xl text-xs font-semibold text-indigo-700 dark:text-indigo-300 shadow-md">
            {{ searchHits().length }} Treffer für "{{ searchInDocQuery }}"
          </div>

          <!-- Canvas Wrapper with Highlights -->
          <div class="relative shadow-xl rounded-lg overflow-hidden bg-white dark:bg-slate-850 border border-slate-200 dark:border-slate-800">
            <!-- PDF Canvas -->
            <canvas #pdfCanvas [class.hidden]="isImage()"></canvas>

            <!-- Fallback for direct images -->
            <img
              *ngIf="isImage()"
              [src]="docService.getFileUrl(docId)"
              [style.transform]="'scale(' + zoom() + ') rotate(' + rotation() + 'deg)'"
              class="max-w-full max-h-full object-contain transition-transform duration-150"
              alt="Dokument Vorschau"
            />

            <!-- In-Doc Search Highlights Overlay -->
            <div
              *ngFor="let h of currentPageHits()"
              [style.left.px]="h.bbox ? h.bbox.x0 * zoom() : 0"
              [style.top.px]="h.bbox ? h.bbox.y0 * zoom() : 0"
              [style.width.px]="h.bbox ? (h.bbox.x1 - h.bbox.x0) * zoom() : 0"
              [style.height.px]="h.bbox ? (h.bbox.y1 - h.bbox.y0) * zoom() : 0"
              class="absolute bg-amber-400/40 border border-amber-500 rounded-xs pointer-events-none"
            ></div>
          </div>
        </div>

        <!-- Right Metadata Sidebar -->
        <aside
          [class.translate-x-0]="metaOpen()"
          [class.translate-x-full]="!metaOpen()"
          class="fixed lg:static inset-y-0 right-0 z-30 w-80 sm:w-96 bg-white dark:bg-slate-850 border-l border-slate-200 dark:border-slate-800 flex flex-col transition-transform duration-200 ease-in-out lg:translate-x-0 shrink-0 shadow-lg lg:shadow-none"
        >
          <!-- Sidebar Header -->
          <div class="p-4 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
            <h3 class="font-bold text-sm">Metadaten & Eigenschaften</h3>
            <button
              type="button"
              (click)="metaOpen.set(false)"
              class="p-1 rounded-lg text-slate-400 hover:text-slate-600 lg:hidden touch-target"
            >
              <app-icon name="x" [size]="18"></app-icon>
            </button>
          </div>

          <!-- Metadata Form -->
          <div class="flex-1 overflow-y-auto p-4 space-y-4 text-xs">
            <!-- Review Status Banner -->
            <div
              *ngIf="doc()?.classification_state === 'needs_review'"
              class="p-3 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800/80 rounded-xl space-y-2"
            >
              <div class="flex items-center gap-2 text-amber-700 dark:text-amber-300 font-bold">
                <app-icon name="alert-triangle" [size]="16"></app-icon>
                <span>Prüfung erforderlich</span>
              </div>
              <p class="text-slate-600 dark:text-slate-300 text-[11px]">
                Bitte überprüfen Sie extrahierte Daten und Tags.
              </p>
              <button
                type="button"
                (click)="resolveReview()"
                class="w-full py-1.5 bg-amber-500 hover:bg-amber-600 text-white rounded-lg font-semibold touch-target transition shadow-xs"
              >
                Als geprüft markieren
              </button>
            </div>

            <!-- Title Field -->
            <div>
              <label class="block font-semibold text-slate-500 mb-1">Titel</label>
              <input
                type="text"
                [(ngModel)]="editTitle"
                class="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl focus:outline-hidden focus:border-indigo-500"
              />
            </div>

            <!-- Sender Field -->
            <div>
              <label class="block font-semibold text-slate-500 mb-1">Absender / Partner</label>
              <input
                type="text"
                [(ngModel)]="editSender"
                placeholder="z.B. Stadtwerke, Amazon"
                class="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl focus:outline-hidden focus:border-indigo-500"
              />
            </div>

            <!-- Date Field -->
            <div>
              <label class="block font-semibold text-slate-500 mb-1">Belegdatum</label>
              <input
                type="date"
                [(ngModel)]="editDate"
                class="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl focus:outline-hidden focus:border-indigo-500"
              />
            </div>

            <!-- Amount & Currency -->
            <div class="grid grid-cols-2 gap-2">
              <div>
                <label class="block font-semibold text-slate-500 mb-1">Betrag</label>
                <input
                  type="number"
                  step="0.01"
                  [(ngModel)]="editAmount"
                  placeholder="0.00"
                  class="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl focus:outline-hidden focus:border-indigo-500"
                />
              </div>
              <div>
                <label class="block font-semibold text-slate-500 mb-1">Währung</label>
                <input
                  type="text"
                  [(ngModel)]="editCurrency"
                  placeholder="EUR"
                  class="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl focus:outline-hidden focus:border-indigo-500"
                />
              </div>
            </div>

            <!-- Tags Section -->
            <div class="space-y-2 pt-2 border-t border-slate-100 dark:border-slate-800">
              <label class="block font-semibold text-slate-500">Zugewiesene Tags</label>
              <div class="flex items-center gap-1.5 flex-wrap min-h-7">
                <span
                  *ngFor="let t of doc()?.tags"
                  class="px-2.5 py-1 text-xs font-medium rounded-lg flex items-center gap-1.5"
                  [style.backgroundColor]="t.color + '20'"
                  [style.color]="t.color"
                >
                  <span>{{ t.name }}</span>
                  <button
                    type="button"
                    (click)="removeTag(t.id)"
                    class="hover:opacity-75 touch-target flex items-center justify-center"
                  >
                    <app-icon name="x" [size]="12"></app-icon>
                  </button>
                </span>
              </div>

              <!-- Add Tag Dropdown -->
              <div class="flex items-center gap-2">
                <select
                  [(ngModel)]="tagToAdd"
                  class="flex-1 px-3 py-1.5 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl text-xs focus:outline-hidden"
                >
                  <option [ngValue]="null">Tag auswählen...</option>
                  <option *ngFor="let at of availableTags()" [value]="at.id">
                    {{ at.name }}
                  </option>
                </select>
                <button
                  type="button"
                  (click)="addTag()"
                  [disabled]="!tagToAdd"
                  class="px-3 py-1.5 bg-slate-200 dark:bg-slate-700 hover:bg-indigo-600 hover:text-white disabled:opacity-40 rounded-xl font-medium touch-target transition"
                >
                  Hinzufügen
                </button>
              </div>
            </div>

            <!-- Folders Section -->
            <div class="space-y-2 pt-2 border-t border-slate-100 dark:border-slate-800">
              <label class="block font-semibold text-slate-500">Ordner</label>
              <select
                [(ngModel)]="selectedFolderId"
                (change)="onFolderChange()"
                class="w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl text-xs focus:outline-hidden"
              >
                <option [value]="''">Kein Ordner (Wurzelverzeichnis)</option>
                <option *ngFor="let f of folderService.folders()" [value]="f.id">
                  {{ f.name }}
                </option>
              </select>
            </div>

            <!-- Save Changes Button -->
            <div class="pt-3">
              <button
                type="button"
                (click)="saveMetadata()"
                [disabled]="saving()"
                class="w-full py-2.5 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-xl font-semibold touch-target transition shadow-xs flex items-center justify-center gap-2"
              >
                <app-icon name="check" [size]="16"></app-icon>
                <span>{{ saving() ? 'Speichern...' : 'Änderungen speichern' }}</span>
              </button>
            </div>

            <!-- Danger Zone -->
            <div class="pt-4 border-t border-slate-100 dark:border-slate-800">
              <button
                type="button"
                (click)="deleteDocument()"
                class="w-full py-2 bg-rose-50 dark:bg-rose-950/40 hover:bg-rose-100 text-rose-600 dark:text-rose-400 rounded-xl font-medium touch-target transition flex items-center justify-center gap-2"
              >
                <app-icon name="trash" [size]="14"></app-icon>
                <span>Dokument löschen</span>
              </button>
            </div>
          </div>
        </aside>
      </div>
    </div>
  `
})
export class DocumentViewerComponent implements OnInit, OnDestroy {
  docService = inject(DocumentService);
  tagService = inject(TagService);
  folderService = inject(FolderService);
  route = inject(ActivatedRoute);
  router = inject(Router);

  Math = Math;
  docId: string = '';
  doc = signal<Document | null>(null);
  manifest = signal<DocumentViewerManifest | null>(null);

  currentPage = signal<number>(1);
  totalPages = signal<number>(1);
  zoom = signal<number>(1.2);
  rotation = signal<number>(0);
  metaOpen = signal<boolean>(false);
  saving = signal<boolean>(false);

  // Form edit fields
  editTitle: string = '';
  editSender: string = '';
  editDate: string = '';
  editAmount: number | null = null;
  editCurrency: string = 'EUR';
  tagToAdd: string | null = null;
  selectedFolderId: string = '';

  // In doc search
  searchInDocQuery: string = '';
  searchHits = signal<InDocSearchHit[]>([]);

  @ViewChild('pdfCanvas') canvasRef?: ElementRef<HTMLCanvasElement>;
  private pdfDoc: any = null;

  ngOnInit() {
    pdfjsLib.GlobalWorkerOptions.workerSrc = '/pdf.worker.min.mjs';

    this.route.params.subscribe(params => {
      this.docId = params['id'];
      this.loadDocumentData();
    });

    this.tagService.loadTags().subscribe();
    this.folderService.loadFolders().subscribe();
  }

  isImage(): boolean {
    const mime = this.doc()?.mime_type || '';
    return mime.startsWith('image/');
  }

  loadDocumentData() {
    this.docService.get(this.docId).subscribe(doc => {
      this.doc.set(doc);
      this.editTitle = doc.title || doc.original_name;
      this.editSender = doc.sender || '';
      this.editDate = doc.document_date || '';
      this.editAmount = doc.amount ? doc.amount / 100 : null;
      this.editCurrency = doc.currency || 'EUR';
      this.selectedFolderId = doc.folders?.[0]?.id || '';

      if (!this.isImage()) {
        this.loadPdf();
      }
    });

    this.docService.getViewerManifest(this.docId).subscribe(man => {
      this.manifest.set(man);
      this.totalPages.set(man.total_pages || 1);
    });
  }

  async loadPdf() {
    try {
      const loadingTask = pdfjsLib.getDocument({
        url: this.docService.getFileUrl(this.docId),
        withCredentials: true
      });
      this.pdfDoc = await loadingTask.promise;
      this.totalPages.set(this.pdfDoc.numPages);
      this.renderPage(this.currentPage());
    } catch (err) {
      console.error('Error loading PDF:', err);
    }
  }

  async renderPage(num: number) {
    if (!this.pdfDoc || !this.canvasRef) return;
    try {
      const page = await this.pdfDoc.getPage(num);
      const viewport = page.getViewport({ scale: this.zoom(), rotation: this.rotation() });
      const canvas = this.canvasRef.nativeElement;
      const context = canvas.getContext('2d')!;

      canvas.height = viewport.height;
      canvas.width = viewport.width;

      const renderContext = {
        canvasContext: context,
        viewport: viewport
      };
      await page.render(renderContext).promise;
    } catch (err) {
      console.error('Error rendering page:', err);
    }
  }

  prevPage() {
    if (this.currentPage() > 1) {
      this.goToPage(this.currentPage() - 1);
    }
  }

  nextPage() {
    if (this.currentPage() < this.totalPages()) {
      this.goToPage(this.currentPage() + 1);
    }
  }

  goToPage(num: number) {
    this.currentPage.set(num);
    if (!this.isImage()) {
      this.renderPage(num);
    }
  }

  zoomIn() {
    this.zoom.update(z => Math.min(3.0, z + 0.2));
    if (!this.isImage()) this.renderPage(this.currentPage());
  }

  zoomOut() {
    this.zoom.update(z => Math.max(0.4, z - 0.2));
    if (!this.isImage()) this.renderPage(this.currentPage());
  }

  rotate() {
    this.rotation.update(r => (r + 90) % 360);
    if (!this.isImage()) this.renderPage(this.currentPage());
  }

  onSearchInDoc() {
    if (!this.searchInDocQuery.trim()) {
      this.searchHits.set([]);
      return;
    }
    this.docService.searchInDocument(this.docId, this.searchInDocQuery.trim()).subscribe(res => {
      this.searchHits.set(res.hits);
      if (res.hits.length > 0) {
        this.goToPage(res.hits[0].page_number);
      }
    });
  }

  currentPageHits(): InDocSearchHit[] {
    return this.searchHits().filter(h => h.page_number === this.currentPage());
  }

  availableTags(): TagResponse[] {
    const existing = new Set((this.doc()?.tags || []).map(t => t.id));
    return this.tagService.tags().filter(t => !existing.has(t.id));
  }

  addTag() {
    if (!this.tagToAdd) return;
    this.tagService.assignToDocument(this.docId, this.tagToAdd).subscribe(() => {
      this.tagToAdd = null;
      this.loadDocumentData();
    });
  }

  removeTag(tagId: string) {
    this.tagService.removeFromDocument(this.docId, tagId).subscribe(() => {
      this.loadDocumentData();
    });
  }

  onFolderChange() {
    if (this.selectedFolderId) {
      this.folderService.addDocumentToFolder(this.docId, this.selectedFolderId).subscribe(() => {
        this.loadDocumentData();
      });
    }
  }

  saveMetadata() {
    this.saving.set(true);
    const amountCents = this.editAmount != null ? Math.round(this.editAmount * 100) : null;
    this.docService.patch(this.docId, {
      title: this.editTitle,
      sender: this.editSender,
      document_date: this.editDate || null,
      amount: amountCents,
      currency: this.editCurrency
    }).subscribe({
      next: (updated) => {
        this.doc.set(updated);
        this.saving.set(false);
      },
      error: () => this.saving.set(false)
    });
  }

  resolveReview() {
    this.docService.patch(this.docId, {
      resolve_review: true
    }).subscribe(updated => {
      this.doc.set(updated);
    });
  }

  deleteDocument() {
    if (!confirm('Dokument wirklich löschen?')) return;
    this.docService.delete(this.docId).subscribe(() => {
      this.router.navigate(['/documents']);
    });
  }

  formatSize(bytes: number): string {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  }

  onThumbError(event: any) {
    event.target.style.display = 'none';
  }

  ngOnDestroy() {
    this.pdfDoc = null;
  }
}

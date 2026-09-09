import { Component, inject, signal, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule, Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { AuthService } from '../../core/services/auth.service';
import { ThemeService } from '../../core/services/theme.service';
import { PollingService } from '../../core/services/polling.service';
import { ReviewService } from '../../core/services/review.service';
import { TagService, TagResponse } from '../../core/services/tag.service';
import { FolderService, FolderNode } from '../../core/services/folder.service';
import { IconComponent } from '../../shared/components/icon/icon.component';

@Component({
  selector: 'app-layout',
  standalone: true,
  imports: [CommonModule, RouterModule, FormsModule, IconComponent],
  template: `
    <div class="min-h-screen flex flex-col bg-slate-50 dark:bg-slate-900 text-slate-800 dark:text-slate-100 transition-colors">
      <!-- Top Navbar -->
      <header class="sticky top-0 z-40 bg-white/90 dark:bg-slate-850/90 backdrop-blur border-b border-slate-200 dark:border-slate-800 px-4 py-2.5 flex items-center justify-between shadow-xs">
        <!-- Brand & Hamburger -->
        <div class="flex items-center gap-3">
          <button
            type="button"
            (click)="sidebarOpen.set(!sidebarOpen())"
            class="md:hidden p-2 rounded-lg text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 touch-target flex items-center justify-center"
            aria-label="Toggle Navigation"
          >
            <app-icon name="menu" [size]="22"></app-icon>
          </button>
          
          <a routerLink="/documents" class="flex items-center gap-2 font-bold text-lg text-indigo-600 dark:text-indigo-400">
            <div class="p-1.5 bg-indigo-100 dark:bg-indigo-950/60 rounded-lg text-indigo-600 dark:text-indigo-400">
              <app-icon name="file-text" [size]="20"></app-icon>
            </div>
            <span class="tracking-tight">Paperless</span>
          </a>
        </div>

        <!-- Global Search Bar -->
        <div class="flex-1 max-w-lg mx-4 hidden sm:block">
          <div class="relative">
            <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
              <app-icon name="search" [size]="18"></app-icon>
            </div>
            <input
              type="search"
              [(ngModel)]="searchQuery"
              (keydown.enter)="onSearch()"
              placeholder="Dokumente durchsuchen (Volltext, Tags, Absender)..."
              class="w-full pl-10 pr-4 py-2 text-sm bg-slate-100 dark:bg-slate-800 border border-transparent dark:border-slate-700 rounded-xl focus:bg-white dark:focus:bg-slate-850 focus:border-indigo-500 focus:outline-hidden transition"
            />
          </div>
        </div>

        <!-- Right Quick Actions -->
        <div class="flex items-center gap-1 sm:gap-2">
          <!-- Active Jobs Pill -->
          <div
            *ngIf="polling.totalActiveJobs() > 0"
            class="flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium bg-amber-50 dark:bg-amber-950/60 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-800/80 rounded-full animate-pulse"
            title="Hintergrundverarbeitung läuft"
          >
            <app-icon name="refresh-cw" [size]="14" extraClass="animate-spin"></app-icon>
            <span>{{ polling.totalActiveJobs() }} aktiv</span>
          </div>

          <!-- Upload Button -->
          <a
            routerLink="/batch-upload"
            class="p-2 sm:px-3 sm:py-2 rounded-xl text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 flex items-center gap-2 touch-target text-sm font-medium transition"
            title="Upload"
          >
            <app-icon name="upload" [size]="18"></app-icon>
            <span class="hidden md:inline">Hochladen</span>
          </a>

          <!-- Camera Scan Button -->
          <a
            routerLink="/camera"
            class="p-2 sm:px-3 sm:py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl flex items-center gap-2 touch-target text-sm font-medium transition shadow-xs"
            title="Kamera-Scan"
          >
            <app-icon name="camera" [size]="18"></app-icon>
            <span class="hidden md:inline">Scannen</span>
          </a>

          <!-- Theme Toggle -->
          <button
            type="button"
            (click)="toggleTheme()"
            class="p-2 rounded-xl text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 touch-target flex items-center justify-center transition"
            [title]="themeService.isDark() ? 'Helles Design' : 'Dunkles Design'"
          >
            <app-icon [name]="themeService.isDark() ? 'sun' : 'moon'" [size]="18"></app-icon>
          </button>

          <!-- Settings -->
          <a
            routerLink="/settings"
            class="p-2 rounded-xl text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 touch-target flex items-center justify-center transition"
            title="Einstellungen"
          >
            <app-icon name="settings" [size]="18"></app-icon>
          </a>

          <!-- Logout -->
          <button
            type="button"
            (click)="logout()"
            class="p-2 rounded-xl text-slate-600 dark:text-slate-300 hover:bg-rose-50 hover:text-rose-600 dark:hover:bg-rose-950/40 dark:hover:text-rose-400 touch-target flex items-center justify-center transition"
            title="Abmelden"
          >
            <app-icon name="log-out" [size]="18"></app-icon>
          </button>
        </div>
      </header>

      <!-- Main Layout Body -->
      <div class="flex-1 flex overflow-hidden">
        <!-- Sidebar Backdrop (Mobile) -->
        <div
          *ngIf="sidebarOpen()"
          (click)="sidebarOpen.set(false)"
          class="fixed inset-0 bg-black/40 z-30 md:hidden backdrop-blur-xs transition-opacity"
        ></div>

        <!-- Sidebar -->
        <aside
          [class.translate-x-0]="sidebarOpen()"
          [class.-translate-x-full]="!sidebarOpen()"
          class="fixed md:static inset-y-0 left-0 z-30 w-64 bg-white dark:bg-slate-850 border-r border-slate-200 dark:border-slate-800 flex flex-col transition-transform duration-200 ease-in-out md:translate-x-0 pt-16 md:pt-0 shrink-0"
        >
          <div class="flex-1 overflow-y-auto p-3 space-y-6">
            <!-- Navigation Links -->
            <div class="space-y-1">
              <a
                routerLink="/documents"
                routerLinkActive="bg-indigo-50 dark:bg-indigo-950/50 text-indigo-600 dark:text-indigo-400 font-semibold"
                [routerLinkActiveOptions]="{ exact: true }"
                (click)="onNavClick()"
                class="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 touch-target transition"
              >
                <app-icon name="file-text" [size]="18"></app-icon>
                <span>Alle Dokumente</span>
              </a>

              <a
                routerLink="/review"
                routerLinkActive="bg-indigo-50 dark:bg-indigo-950/50 text-indigo-600 dark:text-indigo-400 font-semibold"
                (click)="onNavClick()"
                class="flex items-center justify-between px-3 py-2.5 rounded-xl text-sm text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 touch-target transition"
              >
                <div class="flex items-center gap-3">
                  <app-icon name="alert-triangle" [size]="18" extraClass="text-amber-500"></app-icon>
                  <span>Zu prüfen</span>
                </div>
                <span
                  *ngIf="reviewService.needsReviewCount() > 0"
                  class="px-2 py-0.5 text-xs font-bold bg-amber-100 dark:bg-amber-900/60 text-amber-700 dark:text-amber-300 rounded-full"
                >
                  {{ reviewService.needsReviewCount() }}
                </span>
              </a>
            </div>

            <!-- Pinned Tags Section -->
            <div>
              <div class="px-3 mb-2 flex items-center justify-between text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">
                <span>Tags</span>
                <button
                  type="button"
                  (click)="showTagModal.set(true)"
                  class="p-1 hover:text-indigo-600 dark:hover:text-indigo-400 touch-target flex items-center justify-center"
                  title="Tag erstellen"
                >
                  <app-icon name="plus" [size]="14"></app-icon>
                </button>
              </div>

              <div class="space-y-0.5">
                <button
                  *ngFor="let t of tagService.tags()"
                  type="button"
                  (click)="filterByTag(t)"
                  class="w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs text-left text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 touch-target transition"
                >
                  <div class="flex items-center gap-2 truncate">
                    <span class="w-2.5 h-2.5 rounded-full shrink-0" [style.backgroundColor]="t.color"></span>
                    <span class="truncate">{{ t.name }}</span>
                  </div>
                  <span *ngIf="t.document_count" class="text-slate-400 text-[11px]">{{ t.document_count }}</span>
                </button>
              </div>
            </div>

            <!-- Folders Section -->
            <div>
              <div class="px-3 mb-2 flex items-center justify-between text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">
                <span>Ordner</span>
                <button
                  type="button"
                  (click)="showFolderModal.set(true)"
                  class="p-1 hover:text-indigo-600 dark:hover:text-indigo-400 touch-target flex items-center justify-center"
                  title="Ordner erstellen"
                >
                  <app-icon name="plus" [size]="14"></app-icon>
                </button>
              </div>

              <div class="space-y-0.5">
                <button
                  *ngFor="let f of folderService.folders()"
                  type="button"
                  (click)="filterByFolder(f)"
                  class="w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs text-left text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 touch-target transition"
                >
                  <div class="flex items-center gap-2 truncate">
                    <app-icon name="folder" [size]="16" extraClass="text-indigo-500 shrink-0"></app-icon>
                    <span class="truncate">{{ f.name }}</span>
                  </div>
                  <span *ngIf="f.document_count" class="text-slate-400 text-[11px]">{{ f.document_count }}</span>
                </button>
              </div>
            </div>
          </div>

          <!-- Bottom user bar in sidebar -->
          <div class="p-3 border-t border-slate-200 dark:border-slate-800 flex items-center justify-between text-xs text-slate-500">
            <span class="truncate">Angemeldet als <strong>{{ authService.currentUser() }}</strong></span>
          </div>
        </aside>

        <!-- Main Content View -->
        <main class="flex-1 overflow-y-auto p-4 sm:p-6 pb-20 md:pb-6">
          <router-outlet></router-outlet>
        </main>
      </div>

      <!-- Mobile Bottom Navigation Bar -->
      <nav class="md:hidden fixed bottom-0 inset-x-0 bg-white/95 dark:bg-slate-850/95 backdrop-blur border-t border-slate-200 dark:border-slate-800 z-30 flex items-center justify-around py-1">
        <a
          routerLink="/documents"
          routerLinkActive="text-indigo-600 dark:text-indigo-400 font-semibold"
          [routerLinkActiveOptions]="{ exact: true }"
          class="flex flex-col items-center justify-center py-1 px-3 text-[11px] text-slate-600 dark:text-slate-300 touch-target"
        >
          <app-icon name="file-text" [size]="20"></app-icon>
          <span>Dokumente</span>
        </a>

        <a
          routerLink="/review"
          routerLinkActive="text-indigo-600 dark:text-indigo-400 font-semibold"
          class="relative flex flex-col items-center justify-center py-1 px-3 text-[11px] text-slate-600 dark:text-slate-300 touch-target"
        >
          <div class="relative">
            <app-icon name="alert-triangle" [size]="20"></app-icon>
            <span
              *ngIf="reviewService.needsReviewCount() > 0"
              class="absolute -top-1 -right-2 w-4 h-4 bg-amber-500 text-white rounded-full flex items-center justify-center text-[9px] font-bold"
            >
              {{ reviewService.needsReviewCount() }}
            </span>
          </div>
          <span>Prüfen</span>
        </a>

        <a
          routerLink="/camera"
          routerLinkActive="text-indigo-600 dark:text-indigo-400 font-semibold"
          class="flex flex-col items-center justify-center py-1 px-3 text-[11px] text-indigo-600 dark:text-indigo-400 font-semibold touch-target"
        >
          <div class="p-2 -mt-5 bg-indigo-600 text-white rounded-full shadow-lg">
            <app-icon name="camera" [size]="22"></app-icon>
          </div>
          <span>Scan</span>
        </a>

        <a
          routerLink="/batch-upload"
          routerLinkActive="text-indigo-600 dark:text-indigo-400 font-semibold"
          class="flex flex-col items-center justify-center py-1 px-3 text-[11px] text-slate-600 dark:text-slate-300 touch-target"
        >
          <app-icon name="upload" [size]="20"></app-icon>
          <span>Upload</span>
        </a>

        <a
          routerLink="/settings"
          routerLinkActive="text-indigo-600 dark:text-indigo-400 font-semibold"
          class="flex flex-col items-center justify-center py-1 px-3 text-[11px] text-slate-600 dark:text-slate-300 touch-target"
        >
          <app-icon name="settings" [size]="20"></app-icon>
          <span>Setup</span>
        </a>
      </nav>

      <!-- Create Tag Modal -->
      <div *ngIf="showTagModal()" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs">
        <div class="bg-white dark:bg-slate-850 rounded-2xl shadow-xl max-w-sm w-full p-5 space-y-4">
          <h3 class="text-base font-bold">Neuen Tag erstellen</h3>
          <div>
            <label class="block text-xs font-semibold mb-1 text-slate-500">Name</label>
            <input
              type="text"
              [(ngModel)]="newTagName"
              placeholder="z.B. Steuerberater"
              class="w-full px-3 py-2 text-sm bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl focus:outline-hidden focus:border-indigo-500"
            />
          </div>
          <div>
            <label class="block text-xs font-semibold mb-1 text-slate-500">Farbe</label>
            <div class="flex items-center gap-2">
              <input type="color" [(ngModel)]="newTagColor" class="w-10 h-10 rounded-lg cursor-pointer border-0 bg-transparent" />
              <span class="text-xs text-slate-500">{{ newTagColor }}</span>
            </div>
          </div>
          <div class="flex items-center justify-end gap-2 pt-2">
            <button
              type="button"
              (click)="showTagModal.set(false)"
              class="px-4 py-2 text-sm rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800 touch-target"
            >
              Abbrechen
            </button>
            <button
              type="button"
              (click)="createTag()"
              [disabled]="!newTagName.trim()"
              class="px-4 py-2 text-sm bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-xl touch-target font-medium"
            >
              Erstellen
            </button>
          </div>
        </div>
      </div>

      <!-- Create Folder Modal -->
      <div *ngIf="showFolderModal()" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs">
        <div class="bg-white dark:bg-slate-850 rounded-2xl shadow-xl max-w-sm w-full p-5 space-y-4">
          <h3 class="text-base font-bold">Neuen Ordner erstellen</h3>
          <div>
            <label class="block text-xs font-semibold mb-1 text-slate-500">Name</label>
            <input
              type="text"
              [(ngModel)]="newFolderName"
              placeholder="z.B. Rechnungen 2026"
              class="w-full px-3 py-2 text-sm bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl focus:outline-hidden focus:border-indigo-500"
            />
          </div>
          <div class="flex items-center justify-end gap-2 pt-2">
            <button
              type="button"
              (click)="showFolderModal.set(false)"
              class="px-4 py-2 text-sm rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800 touch-target"
            >
              Abbrechen
            </button>
            <button
              type="button"
              (click)="createFolder()"
              [disabled]="!newFolderName.trim()"
              class="px-4 py-2 text-sm bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-xl touch-target font-medium"
            >
              Erstellen
            </button>
          </div>
        </div>
      </div>
    </div>
  `
})
export class LayoutComponent implements OnInit {
  authService = inject(AuthService);
  themeService = inject(ThemeService);
  polling = inject(PollingService);
  reviewService = inject(ReviewService);
  tagService = inject(TagService);
  folderService = inject(FolderService);
  router = inject(Router);

  sidebarOpen = signal<boolean>(false);
  searchQuery: string = '';

  showTagModal = signal<boolean>(false);
  newTagName: string = '';
  newTagColor: string = '#6366f1';

  showFolderModal = signal<boolean>(false);
  newFolderName: string = '';

  ngOnInit() {
    this.tagService.loadTags().subscribe();
    this.folderService.loadFolders().subscribe();
    this.reviewService.loadNeedsReviewCount().subscribe();
  }

  onSearch() {
    if (this.searchQuery.trim()) {
      this.router.navigate(['/documents'], { queryParams: { q: this.searchQuery.trim() } });
    }
  }

  onNavClick() {
    this.sidebarOpen.set(false);
  }

  filterByTag(tag: TagResponse) {
    this.sidebarOpen.set(false);
    this.router.navigate(['/documents'], { queryParams: { tag: tag.id } });
  }

  filterByFolder(folder: FolderNode) {
    this.sidebarOpen.set(false);
    this.router.navigate(['/documents'], { queryParams: { folder: folder.id } });
  }

  toggleTheme() {
    this.themeService.setTheme(this.themeService.isDark() ? 'light' : 'dark');
  }

  createTag() {
    if (!this.newTagName.trim()) return;
    this.tagService.createOrResolve(this.newTagName.trim(), this.newTagColor).subscribe(() => {
      this.newTagName = '';
      this.showTagModal.set(false);
    });
  }

  createFolder() {
    if (!this.newFolderName.trim()) return;
    this.folderService.create(this.newFolderName.trim()).subscribe(() => {
      this.newFolderName = '';
      this.showFolderModal.set(false);
    });
  }

  logout() {
    this.authService.logout().subscribe();
  }
}

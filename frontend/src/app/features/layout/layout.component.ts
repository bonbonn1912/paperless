import { Component, inject, signal, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule, Router, NavigationEnd, IsActiveMatchOptions } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { DestroyRef } from '@angular/core';
import { DialogDirective } from '../../shared/directives/dialog.directive';
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
  imports: [CommonModule, RouterModule, FormsModule, IconComponent, DialogDirective],
  templateUrl: './layout.component.html'
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
  tagsOpen = signal<boolean>(false);
  searchQuery: string = '';

  showTagModal = signal<boolean>(false);
  newTagName: string = '';
  newTagColor: string = '#285941';

  showFolderModal = signal<boolean>(false);
  newFolderName: string = '';

  private destroyRef = inject(DestroyRef);
  readonly navMatch: IsActiveMatchOptions = { paths: 'exact', queryParams: 'ignored', fragment: 'ignored', matrixParams: 'ignored' };
  activeTag = signal<string | null>(null);
  activeFolder = signal<string | null>(null);
  pageLabel = signal('Dokumente');
  creating = signal(false);
  createError = signal<string | null>(null);

  private updateNavigation() {
    const url = this.router.parseUrl(this.router.url);
    this.activeTag.set(url.queryParams['tag'] || null);
    this.activeFolder.set(url.queryParams['folder'] || null);
    const path = this.router.url.split('?')[0];
    this.pageLabel.set(path === '/review' ? 'Zu prüfen' : path === '/settings' ? 'Einstellungen' : path === '/camera' ? 'Scannen' : path === '/batch-upload' ? 'Import & Verarbeitung' : path.startsWith('/documents/') ? 'Dokumentansicht' : 'Dokumente');
  }
  ngOnInit() {
    this.updateNavigation();
    this.router.events.pipe(takeUntilDestroyed(this.destroyRef)).subscribe(event => { if (event instanceof NavigationEnd) this.updateNavigation(); });
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
    this.creating.set(true); this.createError.set(null);
    this.tagService.createOrResolve(this.newTagName.trim(), this.newTagColor).subscribe({ next: () => { this.newTagName = ''; this.showTagModal.set(false); this.creating.set(false); }, error: () => { this.creating.set(false); this.createError.set('Der Tag konnte nicht erstellt werden. Bitte erneut versuchen.'); } });
  }

  createFolder() {
    if (!this.newFolderName.trim()) return;
    this.creating.set(true); this.createError.set(null);
    this.folderService.create(this.newFolderName.trim()).subscribe({ next: () => { this.newFolderName = ''; this.showFolderModal.set(false); this.creating.set(false); }, error: () => { this.creating.set(false); this.createError.set('Der Ordner konnte nicht erstellt werden. Bitte erneut versuchen.'); } });
  }

  logout() {
    this.authService.logout().subscribe();
  }
}

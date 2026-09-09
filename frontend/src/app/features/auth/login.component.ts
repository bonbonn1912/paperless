import { Component, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, ActivatedRoute } from '@angular/router';
import { AuthService } from '../../core/services/auth.service';
import { IconComponent } from '../../shared/components/icon/icon.component';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, FormsModule, IconComponent],
  template: `
    <div class="min-h-screen flex items-center justify-center bg-slate-100 dark:bg-slate-900 p-4 transition-colors">
      <div class="max-w-md w-full bg-white dark:bg-slate-850 rounded-3xl shadow-xl border border-slate-200 dark:border-slate-800 p-8 space-y-6">
        <div class="text-center space-y-2">
          <div class="inline-flex p-3 bg-indigo-100 dark:bg-indigo-950/60 rounded-2xl text-indigo-600 dark:text-indigo-400">
            <app-icon name="file-text" [size]="32"></app-icon>
          </div>
          <h1 class="text-2xl font-black tracking-tight text-slate-800 dark:text-slate-100">Paperless</h1>
          <p class="text-xs text-slate-500">Lokales Dokumenten-Management-System</p>
        </div>

        <div *ngIf="errorMessage()" class="p-3 text-xs bg-rose-50 dark:bg-rose-950/50 text-rose-600 dark:text-rose-400 border border-rose-200 dark:border-rose-900 rounded-xl flex items-center gap-2">
          <app-icon name="alert-triangle" [size]="16"></app-icon>
          <span>{{ errorMessage() }}</span>
        </div>

        <form (ngSubmit)="onSubmit()" class="space-y-4">
          <div>
            <label class="block text-xs font-semibold text-slate-600 dark:text-slate-300 mb-1.5">Benutzername</label>
            <input
              type="text"
              name="username"
              [(ngModel)]="username"
              required
              autocomplete="username"
              class="w-full px-4 py-2.5 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl focus:bg-white dark:focus:bg-slate-850 focus:border-indigo-500 focus:outline-hidden transition"
              placeholder="admin"
            />
          </div>

          <div>
            <label class="block text-xs font-semibold text-slate-600 dark:text-slate-300 mb-1.5">Passwort</label>
            <input
              type="password"
              name="password"
              [(ngModel)]="password"
              required
              autocomplete="current-password"
              class="w-full px-4 py-2.5 text-sm bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl focus:bg-white dark:focus:bg-slate-850 focus:border-indigo-500 focus:outline-hidden transition"
              placeholder="••••••••"
            />
          </div>

          <button
            type="submit"
            [disabled]="loading() || !username || !password"
            class="w-full py-3 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white font-semibold text-sm rounded-xl touch-target transition shadow-md flex items-center justify-center gap-2"
          >
            <span *ngIf="loading()" class="animate-spin">
              <app-icon name="refresh-cw" [size]="16"></app-icon>
            </span>
            <span>{{ loading() ? 'Anmelden...' : 'Anmelden' }}</span>
          </button>
        </form>
      </div>
    </div>
  `
})
export class LoginComponent {
  authService = inject(AuthService);
  router = inject(Router);
  route = inject(ActivatedRoute);

  username = '';
  password = '';
  loading = signal<boolean>(false);
  errorMessage = signal<string | null>(null);

  onSubmit() {
    if (!this.username || !this.password) return;

    this.loading.set(true);
    this.errorMessage.set(null);

    this.authService.login(this.username, this.password).subscribe({
      next: () => {
        this.loading.set(false);
        const returnUrl = this.route.snapshot.queryParams['returnUrl'] || '/documents';
        this.router.navigateByUrl(returnUrl);
      },
      error: (err) => {
        this.loading.set(false);
        this.errorMessage.set(err.error?.detail || 'Ungültige Anmeldedaten');
      }
    });
  }
}

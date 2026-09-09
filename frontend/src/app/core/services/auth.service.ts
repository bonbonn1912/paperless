import { Injectable, signal, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, tap, catchError, of } from 'rxjs';
import { Router } from '@angular/router';

export interface LoginResponse {
  username: string;
  csrf_token: string;
  message: string;
}

export interface MeResponse {
  username: string;
  is_authenticated: boolean;
  csrf_token: string;
}

@Injectable({
  providedIn: 'root'
})
export class AuthService {
  private http = inject(HttpClient);
  private router = inject(Router);

  currentUser = signal<string | null>(null);
  isAuthenticated = signal<boolean>(false);
  csrfToken = signal<string | null>(localStorage.getItem('paperless_csrf'));
  isLoading = signal<boolean>(true);

  checkAuth(): Observable<MeResponse | null> {
    this.isLoading.set(true);
    return this.http.get<MeResponse>('/api/v1/auth/me', { withCredentials: true }).pipe(
      tap({
        next: (res) => {
          this.currentUser.set(res.username);
          this.isAuthenticated.set(res.is_authenticated);
          if (res.csrf_token) {
            this.csrfToken.set(res.csrf_token);
            localStorage.setItem('paperless_csrf', res.csrf_token);
          }
          this.isLoading.set(false);
        },
        error: () => {
          this.currentUser.set(null);
          this.isAuthenticated.set(false);
          this.csrfToken.set(null);
          localStorage.removeItem('paperless_csrf');
          this.isLoading.set(false);
        }
      }),
      catchError(() => {
        this.isLoading.set(false);
        return of(null);
      })
    );
  }

  login(username: string, password: string): Observable<LoginResponse> {
    return this.http.post<LoginResponse>('/api/v1/auth/login', { username, password }, { withCredentials: true }).pipe(
      tap((res) => {
        this.currentUser.set(res.username);
        this.isAuthenticated.set(true);
        if (res.csrf_token) {
          this.csrfToken.set(res.csrf_token);
          localStorage.setItem('paperless_csrf', res.csrf_token);
        }
      })
    );
  }

  logout(): Observable<any> {
    return this.http.post('/api/v1/auth/logout', {}, { withCredentials: true }).pipe(
      tap(() => {
        this.currentUser.set(null);
        this.isAuthenticated.set(false);
        this.csrfToken.set(null);
        localStorage.removeItem('paperless_csrf');
        this.router.navigate(['/login']);
      }),
      catchError(() => {
        this.currentUser.set(null);
        this.isAuthenticated.set(false);
        this.csrfToken.set(null);
        this.router.navigate(['/login']);
        return of(null);
      })
    );
  }
}

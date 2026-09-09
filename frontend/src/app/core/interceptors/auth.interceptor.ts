import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { AuthService } from '../services/auth.service';

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const authService = inject(AuthService);
  const csrfToken = authService.csrfToken();

  let cloned = req.clone({
    withCredentials: true
  });

  const mutatingMethods = ['POST', 'PUT', 'PATCH', 'DELETE'];
  if (mutatingMethods.includes(req.method.toUpperCase()) && csrfToken) {
    cloned = cloned.clone({
      headers: cloned.headers.set('X-CSRF-Token', csrfToken)
    });
  }

  return next(cloned);
};
